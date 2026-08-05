# Source this before running the playbooks:  source setup-env.sh
#
# Two things it handles:
#
# 1. If you already export ANSIBLE_CONFIG for another project, it WINS over the
#    ansible.cfg in this directory, and the playbooks will not find inventory.ini.
#    Ansible only auto-loads ./ansible.cfg when ANSIBLE_CONFIG is unset.
#
# 2. On macOS, force Apple's ssh/sftp/scp. A Homebrew ssh rejects the
#    UseKeychain option that many ~/.ssh/config files set, with an error that
#    does not obviously point at ssh.

_here="$(cd "$(dirname "${BASH_SOURCE[0]:-${(%):-%x}}")" && pwd)"
export ANSIBLE_CONFIG="$_here/ansible.cfg"

if [ "$(uname -s)" = "Darwin" ]; then
    export ANSIBLE_SSH_EXECUTABLE=/usr/bin/ssh
    export ANSIBLE_SFTP_EXECUTABLE=/usr/bin/sftp
    export ANSIBLE_SCP_EXECUTABLE=/usr/bin/scp
fi

echo "ANSIBLE_CONFIG=$ANSIBLE_CONFIG"
unset _here
