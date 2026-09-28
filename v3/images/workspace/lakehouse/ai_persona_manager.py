"""Which Jupyter AI personas exist in a lab workspace (CONTRACT Phase 5; FIX 3 of the Phase 5
follow-up): ONLY personas that talk to the lab's AI gateway (through the AI front door) with
the user's own key.

Jupyter AI v3 loads every persona registered under the `jupyter_ai.personas` entry point
group, plus Python files in `.jupyter/personas/`. The `jupyter-ai` package depends on
`jupyter_ai_acp_client`, which registers ACP personas (claude-acp, codex-acp, copilot-acp,
goose-acp, kilo-acp, kiro-acp, mistral-vibe-acp, opencode-acp): each runs a third-party agent
that talks to ITS OWN provider with its own login, bypassing the gateway's budgets, the lab's
system prompt and tutor mode. The stock Jupyternaut persona lets the user pick any LiteLLM
model string and API base. None of those is gateway-bound, so none is offered.

`LabPersonaManager` (configured in /etc/jupyter/jupyter_server_config.py as
`PersonaManagerExtension.persona_manager_class`) loads exactly the entry points in
ALLOWED_PERSONAS, matched by name AND object reference (a user-installed package cannot
claim the name), and no local persona files. ALLOWED_PERSONAS is the single list of personas
a workspace offers. The "Claude" ACP persona is not kept: it would run Claude Code through
the `claude-agent-acp` adapter (not installed, and not pointed at the gateway); Claude Code in
the lab is the CLI that `lab-ai install-claude-code` installs and points at the gateway.
"""
from importlib_metadata import entry_points
from jupyter_ai_persona_manager.persona_manager import EPG_NAME, PersonaManager
from traitlets import Unicode

from . import ai

# entry point name -> object reference. The ONLY personas a lab workspace offers.
ALLOWED_PERSONAS = {"lab-assistant": "lakehouse.ai_persona:LabAssistant"}


def allowed(ep):
    return ALLOWED_PERSONAS.get(ep.name) == ep.value


class LabPersonaManager(PersonaManager):
    """Jupyter AI's PersonaManager, restricted to ALLOWED_PERSONAS."""

    default_persona_id = Unicode(default_value=ai.PERSONA_ID, allow_none=True, config=True,
                                 help="The lab's default persona (the Lab Assistant).")

    def _init_ep_persona_classes(self):
        classes = []
        for ep in entry_points().select(group=EPG_NAME):
            if not allowed(ep):
                self.log.info("Lab: persona entry point %r (%s) is not offered in the lab "
                              "(not routed through the lab's AI gateway)", ep.name, ep.value)
                continue
            try:
                classes.append({"module": ep.name, "persona_class": ep.load(), "traceback": None})
            except Exception:  # noqa: BLE001 - reported like upstream: one broken persona
                self.log.exception("Lab: could not load persona %r", ep.name)
        PersonaManager._ep_persona_classes = classes

    def _init_local_persona_classes(self):
        # `.jupyter/personas/*.py` would add personas that bypass the gateway as well.
        self._local_persona_classes = []
