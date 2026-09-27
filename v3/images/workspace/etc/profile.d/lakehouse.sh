# shellcheck shell=sh
# Lakehouse Lab workspace (images/workspace): login shells get the lab's commands first.
# JupyterLab terminals run `bash -l`, and Debian's /etc/profile resets PATH, which dropped
# /opt/lakehouse/bin: `lab-tracks: command not found`, and `dbt` ran without the token shim
# (REG_V3_WORKSPACE_LOGIN_SHELL_LOSES_LAB_PATH). /etc/profile sources this file after its
# reset. Idempotent: any existing /opt/lakehouse/bin entry is removed, then it is put first,
# so the dbt shim always wins over /usr/local/bin/dbt. PYTHONPATH and JUPYTERHUB_* come from
# the server's environment (the image's ENV and the spawner); /etc/profile leaves them alone.
_lab_rest=
_lab_ifs=$IFS
IFS=:
for _lab_d in $PATH; do
  [ "$_lab_d" = /opt/lakehouse/bin ] || [ -z "$_lab_d" ] || _lab_rest="${_lab_rest:+$_lab_rest:}$_lab_d"
done
IFS=$_lab_ifs
PATH="/opt/lakehouse/bin${_lab_rest:+:$_lab_rest}"
# User-installed tools (`lab-ai install-claude-code` puts `claude` there) come LAST, so they
# never shadow the lab's commands or the dbt shim.
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) PATH="$PATH:$HOME/.local/bin" ;; esac
export PATH
unset _lab_rest _lab_ifs _lab_d
