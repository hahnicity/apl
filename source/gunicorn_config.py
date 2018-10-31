bind = "unix:/var/tmp/apl.sock"
timeout = 300
workers = 4
max_requests = 10

# well good thing there aren't security implications if this thing gets hacked...
user = "ubuntu"
group = "ubuntu"

accesslog = "/var/log/apl/access.log"
errorlog = "/var/log/apl/error.log"
