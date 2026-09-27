"""The "Lab Assistant" persona for Jupyter AI v3 (CONTRACT Phase 5; ADR-014).

Jupyter AI's own Jupyternaut persona (jupyter-ai[jupyternaut]: LiteLLM + LangChain agent +
MCP tools) with the lab's wiring:

* Model: always the lab's AI gateway, with the user's own virtual key (LAB_AI_* from the hub;
  lakehouse/ai.py `gateway`). The model picker offers only the lab's model. Without a key it
  answers AI_NOT_CONFIGURED and makes no call at all.
* System prompt: lakehouse/ai.py `system_prompt`: the lab context and safety rules (tool
  output is untrusted), plus, in tutor mode inside a track module, that module's tutor.md.
* Tools: in tutor mode only READ tools (read the learner's notebook, which notebook is open)
  and the lab's MCP servers (read-only, acting as the user); no editing or running of cells,
  no shell. Outside tutor mode: Jupyternaut's tools plus every configured MCP server.
* Errors from the gateway (budget exceeded, key refused, no model) get a clear message.

Registered through the entry point `jupyter_ai.personas` (lakehouse_lab_ai.dist-info in
/opt/lakehouse/python) and made the default persona in /etc/jupyter/jupyter_server_config.py.
"""
import asyncio
import os

from jupyter_ai_jupyternaut.jupyternaut.jupyternaut import JupyternautPersona
from jupyter_ai_jupyternaut.jupyternaut.toolkits import notebook as _nb
from jupyter_ai_persona_manager import (McpServerHttp, McpServerStdio, ModelConfiguration,
                                        ModelOption, PersonaDefaults)
from langchain.agents import create_agent
from langchain_litellm import ChatLiteLLM
from langchain_mcp_adapters.client import MultiServerMCPClient

from . import ai

# Tools that only read (tutor mode). Everything that writes or executes is left out.
READ_ONLY_NOTEBOOK_TOOLS = (_nb.read_notebook_cells, _nb.get_active_notebook,
                            _nb.get_active_cell_id, _nb.get_open_documents)
AVATAR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_avatar.svg")


class LabAssistant(JupyternautPersona):
    """Jupyternaut, wired to the lab's gateway, prompt, tutor mode and MCP servers."""

    _tutor_active = False
    _module_id = None

    @property
    def defaults(self):
        return PersonaDefaults(
            name=ai.PERSONA_NAME,
            avatar_path=AVATAR_PATH,
            description=("Lakehouse Lab's assistant: knows the lab's tables, lineage, pipelines "
                         "and your current lesson, and acts only with your permissions. In a "
                         "track module it tutors (hints, not answers)."),
            system_prompt="(built per message: lakehouse/ai.py system_prompt)",
        )

    # ------------------------------------------------------------------ model
    def _build_model_configuration(self):
        gw = ai.gateway()
        options = [ModelOption(id=gw["model"], name=gw["model"],
                               description="The lab's model, through the lab's AI gateway")] \
            if gw["ok"] else []
        return ModelConfiguration(current=None, options=options, settings=[])

    async def update_model(self, model_id):
        """The lab's model is the only choice; nothing to switch."""

    def _resolve_model(self):
        gw = ai.gateway()
        if not gw["ok"]:
            return None, {}
        # LiteLLM's OpenAI-compatible route, to the gateway only, with the user's key.
        return f"openai/{gw['model']}", {"api_base": gw["base_url"], "api_key": gw["key"]}

    async def get_agent(self, model_id, model_args, system_prompt):
        # Upstream ChatLiteLLM (no Anthropic-style cache_control injection: the gateway may
        # route to a local OpenAI-compatible server that does not accept it).
        model = ChatLiteLLM(**model_args, model=model_id, streaming=True)
        return create_agent(model, system_prompt=system_prompt,
                            checkpointer=await self.get_memory_store(),
                            tools=await self.get_tools(),
                            middleware=[self._create_tool_error_handler()])

    # ------------------------------------------------------------------ messages
    async def process_message(self, message):
        gw = ai.gateway()
        if not gw["ok"]:
            self.send_message(ai.not_configured_message(gw))
            return
        # The notebook the learner has open (JupyterLab awareness), for tutor mode's module.
        self._active_path = None
        try:
            self._active_path = await asyncio.wait_for(
                _nb.get_active_notebook(message.sender), timeout=2)
        except Exception:  # noqa: BLE001 - awareness unavailable: decide from the folders
            pass
        await super().process_message(message)

    def send_message(self, body):
        if isinstance(body, str) and body.startswith("Error:"):
            body = ai.friendly_error(body)
        super().send_message(body)

    def get_system_prompt(self, model_id, message):
        context = self.process_attachments(message) or ""
        try:
            chat_dir = self.get_chat_dir()
        except Exception:  # noqa: BLE001 - no chat path: no module from the folder
            chat_dir = None
        active = getattr(self, "_active_path", None)
        prompt, module = ai.system_prompt(chat_dir=chat_dir, username=message.sender,
                                          context=context, model=ai.gateway()["model"],
                                          active_path=active)
        self._tutor_active = module is not None
        try:            # for the lab-context server's current_lesson, tutor mode or not
            here = module or ai.current_module(chat_dir, active)
        except Exception:  # noqa: BLE001 - no tracks: no module
            here = None
        self._module_id = here.id if here else None
        if module is not None:
            self.log.info("Lab Assistant: tutor mode for module %s", module.id)
        return prompt

    # ------------------------------------------------------------------ tools
    async def get_tools(self):
        tutor = self._tutor_active
        tools = list(READ_ONLY_NOTEBOOK_TOOLS) if tutor else await self._jupyternaut_tools()
        lab = {s["name"] for s in ai.lab_mcp_servers()}
        settings = self.get_mcp_settings()
        connections = {}
        for mcp in (settings.mcp_servers if settings else []):
            if tutor and not (isinstance(mcp, McpServerStdio) and mcp.name in lab):
                continue          # tutor mode: only the lab's read-only servers
            if isinstance(mcp, McpServerHttp):
                connections[mcp.name] = {"transport": mcp.type, "url": mcp.url,
                                         "headers": {h.name: h.value for h in mcp.headers}}
            elif isinstance(mcp, McpServerStdio):
                env = {v.name: v.value for v in mcp.env}
                if self._module_id and mcp.name in lab:
                    env["LAB_CURRENT_MODULE"] = self._module_id
                connections[mcp.name] = {"transport": "stdio", "command": mcp.command,
                                         "args": mcp.args, "env": env}
        client = MultiServerMCPClient(connections)
        for name in connections:
            try:
                tools += await client.get_tools(server_name=name)
            except Exception:  # noqa: BLE001 - one broken server must not stop the reply
                self.log.warning("Lab Assistant: MCP server %r unavailable; skipped", name,
                                 exc_info=True)
        return tools

    async def _jupyternaut_tools(self):
        from jupyter_ai_jupyternaut.jupyternaut.toolkits.code_execution import toolkit as ex
        from jupyter_ai_jupyternaut.jupyternaut.toolkits.jupyterlab import toolkit as jl
        return list(_nb.toolkit) + list(jl) + list(ex)
