# Admin UI

This is the Admin UI for the Canonical identity platform.

### Development server

Haproxy needs to be installed

    apt install haproxy

and configured

    vim /etc/haproxy/haproxy.cfg

use this content for the file

    global
      daemon
    
    defaults
      mode  http


    frontend iam_frontend
      bind 172.17.0.1:8000
      default_backend iam_admin_be

    backend iam_admin_be
      server admin_be 127.0.0.1:8000

and restart it

    service haproxy restart

Start the build server as described in the main README.md in the root of this repo

    make dev

Install dotrun as described in https://github.com/canonical/dotrun#installation Launch it from the `ui/` directory of this repo

    dotrun

browse to https://localhost:8411/ to reach iam-admin-ui.