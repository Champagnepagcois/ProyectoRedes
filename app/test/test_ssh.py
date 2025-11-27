import paramiko

hostname = "192.168.0.1"
username = "admin"
password = "n0m3l0"

# Crear cliente
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Forzar kex antiguo
client.connect(
    hostname,
    username=username,
    password=password,
    look_for_keys=False,
    allow_agent=False
)

# Forzar el KEX group1-sha1
transport = client.get_transport()
sec_opts = transport.get_security_options()
sec_opts.kex = ['diffie-hellman-group1-sha1']

stdin, stdout, stderr = client.exec_command("show ip int brief")
print(stdout.read().decode())

client.close()
