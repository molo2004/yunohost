# encoding: utf-8

import os
import re
import pwd
import subprocess

from moulinette.utils.filesystem import read_file, write_to_file


SSHD_CONFIG_PATH = "/etc/ssh/sshd_config"

# user list + root + admin
def ssh_user_list(auth):
    # couldn't resued user_list because it's not customisable enough :(
    user_attrs = {
        'uid': 'username',
        'cn': 'fullname',
        'mail': 'mail',
        'loginShell': 'shell',
        'homeDirectory': 'home_path',
    }

    root_unix = pwd.getpwnam("root")
    root = {
        'username': 'root',
        'fullname': '',
        'mail': '',
        # TODO ssh-allow using ssh_root_login_status
        'ssh_allowed': True,
        'shell': root_unix.pw_shell,
        'home_path': root_unix.pw_dir,
    }

    admin_unix = pwd.getpwnam("root")
    admin = {
        'username': 'admin',
        'fullname': '',
        'mail': '',
        'ssh_allowed': admin_unix.pw_shell.strip() != "/bin/false",
        'shell': admin_unix.pw_shell,
        'home_path': admin_unix.pw_dir,
    }

    query = '(&(objectclass=person)(!(uid=root))(!(uid=nobody)))'
    users = {}

    ldap_result = auth.search('ou=users,dc=yunohost,dc=org', query, user_attrs.keys())

    for user in ldap_result:
        entry = {}

        for key, value in user.items():
            if key == "loginShell":
                if value[0].strip() == "/bin/false":
                    entry["ssh_allowed"] = False
                else:
                    entry["ssh_allowed"] = True

            entry[user_attrs[key]] = value[0]

        uid = entry[user_attrs['uid']]
        users[uid] = entry

    return {
        'root': root,
        'admin': admin,
        'users': users,
    }


def ssh_user_allow_ssh(auth, username):
    # TODO escape input using https://www.python-ldap.org/doc/html/ldap-filter.html
    # TODO it would be good to support different kind of shells

    query = '(&(objectclass=person)(uid=%s))' % username

    # FIXME handle root and admin
    # XXX dry
    if not auth.search('ou=users,dc=yunohost,dc=org', query):
        raise Exception("User with username '%s' doesn't exists")

    auth.update('uid=%s,ou=users' % username, {'loginShell': '/bin/bash'})


def ssh_user_disallow_ssh(auth, username):
    # TODO escape input using https://www.python-ldap.org/doc/html/ldap-filter.html
    # TODO it would be good to support different kind of shells

    query = '(&(objectclass=person)(uid=%s))' % username

    # FIXME handle root and admin
    # XXX dry
    if not auth.search('ou=users,dc=yunohost,dc=org', query):
        raise Exception("User with username '%s' doesn't exists")

    auth.update('uid=%s,ou=users' % username, {'loginShell': '/bin/false'})


# XXX should we support all the options?
def ssh_root_login_status(auth):
    # this is the content of "man sshd_config"
    # PermitRootLogin
    #     Specifies whether root can log in using ssh(1).  The argument must be
    #     “yes”, “without-password”, “forced-commands-only”, or “no”.  The
    #     default is “yes”.
    sshd_config_content = read_file(SSHD_CONFIG_PATH)

    if re.search("^ *PermitRootLogin +(no|forced-commands-only) *$",
                 sshd_config_content, re.MULTILINE):
        return {"PermitRootLogin": False}

    return {"PermitRootLogin": True}


def ssh_root_login_enable(auth):
    sshd_config_content = read_file(SSHD_CONFIG_PATH)
    # TODO rollback to old config if service reload failed
    # sshd_config_content_backup = sshd_config_content

    if re.search("^ *PermitRootLogin +(no|forced-commands-only|yes|without-password) *$",
                 sshd_config_content, re.MULTILINE):

        sshd_config_content = re.sub("^ *PermitRootLogin +(yes|without-password) *$",
                                     "PermitRootLogin yes",
                                     sshd_config_content,
                                     flags=re.MULTILINE)

    else:
        sshd_config_content += "\nPermitRootLogin yes\n"

    write_to_file(SSHD_CONFIG_PATH, sshd_config_content)

    subprocess.check_call("service sshd reload", shell=True)


def ssh_root_login_disable(auth):
    sshd_config_content = read_file(SSHD_CONFIG_PATH)
    # TODO rollback to old config if service reload failed
    # sshd_config_content_backup = sshd_config_content

    if re.search("^ *PermitRootLogin +(no|forced-commands-only|yes|without-password) *$",
                 sshd_config_content, re.MULTILINE):

        sshd_config_content = re.sub("^ *PermitRootLogin +(yes|without-password) *$",
                                     "PermitRootLogin no",
                                     sshd_config_content,
                                     flags=re.MULTILINE)

    else:
        sshd_config_content += "\nPermitRootLogin no\n"

    write_to_file(SSHD_CONFIG_PATH, sshd_config_content)

    subprocess.check_call("service sshd reload", shell=True)


# XXX should we display private key too?
def ssh_key_list(auth, username):
    # TODO escape input using https://www.python-ldap.org/doc/html/ldap-filter.html
    query = '(&(objectclass=person)(uid=%s))' % username
    user = auth.search('ou=users,dc=yunohost,dc=org', query, attrs=["homeDirectory"])

    # FIXME handle root and admin
    # XXX dry
    if not user:
        raise Exception("User with username '%s' doesn't exists")

    user_home_directory = user[0]["homeDirectory"][0]
    ssh_dir = os.path.join(user_home_directory, ".ssh")

    if not os.path.exists(ssh_dir):
        return {"keys": []}

    keys = []

    for i in os.listdir(ssh_dir):
        if i.endswith(".pub"):
            keys.append({
                ".".join(i.split(".")[:-1]): read_file(os.path.join(ssh_dir, i))
            })

    return {
        "keys": keys,
    }


# dsa | ecdsa | ed25519 | rsa | rsa1
# this is the list of valid algo according to the man page
# according to internet ™ rsa seems the one to use for maximum compatibility
# and is still very strong
#
# QUESTION: should we forbid certains algos known to be BAD?
def ssh_key_add(auth, username, algo="default"):
    pass


def ssh_key_import(auth, username, public, private, name=None):
    pass


def ssh_key_remove(auth, username, key):
    pass


def ssh_authorized_keys_list(auth, username):
    pass


def ssh_authorized_keys_add(auth, username, key):
    pass


def ssh_authorized_keys_remove(auth, username, key):
    pass


# TODO
# arguments in actionmap
