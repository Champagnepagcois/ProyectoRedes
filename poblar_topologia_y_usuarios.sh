#!/bin/bash
# ==========================================================
# Script: poblar_topologia_y_usuarios.sh
# Objetivo:
#   - Crear la estructura de routers e interfaces EXACTA
#     del diagrama (Edge, R1, R2, TOR-1, TOR-2)
#   - Crear usuarios globales en todos los routers
# Notas:
#   - La API debe estar corriendo en http://localhost:8000
#   - NO se usa '| jq', solo curl normal
#   - Ajusta IPs si tu práctica las cambió, pero aquí van
#     tal como vienen en el diagrama.
# ==========================================================

BASE="http://localhost:8000"

echo "============================================================"
echo "1) CREACIÓN DE ROUTERS E INTERFACES SEGÚN EL DIAGRAMA"
echo "============================================================"

# --------------------- EDGE ---------------------
echo
echo ">>> Creando router Edge"

curl -X POST "$BASE/routers/" \
-H "Content-Type: application/json" \
-d '{
  "hostname": "Edge",
  "ip_admin": "192.168.100.1",
  "loopback": "192.168.50.1",
  "role": "edge",
  "vendor": "Cisco",
  "os_version": "IOS 15",
  "interfaces": [
    {
      "name": "f1/0",
      "ip_address": "10.0.0.1",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "R1"
    },
    {
      "name": "f1/1",
      "ip_address": "10.0.0.5",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "R2"
    }
  ]
}'

# --------------------- R1 ---------------------
echo
echo ">>> Creando router R1"

curl -X POST "$BASE/routers/" \
-H "Content-Type: application/json" \
-d '{
  "hostname": "R1",
  "ip_admin": "192.168.100.2",
  "loopback": "192.168.50.2",
  "role": "core",
  "vendor": "Cisco",
  "os_version": "IOS 15",
  "interfaces": [
    {
      "name": "f1/0",
      "ip_address": "10.0.0.2",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "Edge"
    },
    {
      "name": "f2/0",
      "ip_address": "10.0.0.17",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "TOR-1"
    },
    {
      "name": "f2/1",
      "ip_address": "10.0.0.9",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "TOR-2"
    }
  ]
}'

# --------------------- R2 ---------------------
echo
echo ">>> Creando router R2"

curl -X POST "$BASE/routers/" \
-H "Content-Type: application/json" \
-d '{
  "hostname": "R2",
  "ip_admin": "192.168.100.3",
  "loopback": "192.168.50.3",
  "role": "core",
  "vendor": "Cisco",
  "os_version": "IOS 15",
  "interfaces": [
    {
      "name": "f1/1",
      "ip_address": "10.0.0.6",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "Edge"
    },
    {
      "name": "f2/1",
      "ip_address": "10.0.0.13",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "TOR-1"
    },
    {
      "name": "f2/0",
      "ip_address": "10.0.0.21",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "TOR-2"
    }
  ]
}'

# --------------------- TOR-1 ---------------------
echo
echo ">>> Creando router TOR-1"

curl -X POST "$BASE/routers/" \
-H "Content-Type: application/json" \
-d '{
  "hostname": "TOR-1",
  "ip_admin": "192.168.100.4",
  "loopback": "192.168.50.4",
  "role": "leaf",
  "vendor": "Cisco",
  "os_version": "IOS 15",
  "interfaces": [
    {
      "name": "f2/0",
      "ip_address": "10.0.0.18",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "R1"
    },
    {
      "name": "f2/1",
      "ip_address": "10.0.0.14",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "R2"
    },
    {
      "name": "f1/0",
      "ip_address": "192.168.0.1",
      "mask": "255.255.255.0",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "Switch1"
    },
    {
      "name": "f1/1",
      "ip_address": "192.168.1.1",
      "mask": "255.255.255.0",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "Switch2"
    }
  ]
}'

# --------------------- TOR-2 ---------------------
echo
echo ">>> Creando router TOR-2"

curl -X POST "$BASE/routers/" \
-H "Content-Type: application/json" \
-d '{
  "hostname": "TOR-2",
  "ip_admin": "192.168.100.5",
  "loopback": "192.168.50.5",
  "role": "leaf",
  "vendor": "Cisco",
  "os_version": "IOS 15",
  "interfaces": [
    {
      "name": "f2/0",
      "ip_address": "10.0.0.10",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "R1"
    },
    {
      "name": "f2/1",
      "ip_address": "10.0.0.22",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "R2"
    },
    {
      "name": "f1/0",
      "ip_address": "192.168.10.1",
      "mask": "255.255.255.0",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "Switch3"
    },
    {
      "name": "f1/1",
      "ip_address": "192.168.11.1",
      "mask": "255.255.255.0",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "Switch4"
    }
  ]
}'

echo
echo "============================================================"
echo "2) CREACIÓN DE USUARIOS GLOBALES EN TODOS LOS ROUTERS"
echo "============================================================"

# Usuario global: operador
echo
echo ">>> Creando usuario global 'operador' (privilege 5, read-only)"
curl -X POST "$BASE/usuarios/" \
-H "Content-Type: application/json" \
-d '{
  "username": "operador",
  "privilege": 5,
  "permissions": "read-only"
}'

# Usuario global: soporte
echo
echo ">>> Creando usuario global 'soporte' (privilege 10, operaciones)"
curl -X POST "$BASE/usuarios/" \
-H "Content-Type: application/json" \
-d '{
  "username": "soporte",
  "privilege": 10,
  "permissions": "operaciones"
}'

echo
echo "============================================================"
echo "3) LISTADO RÁPIDO (OPCIONAL) DE ROUTERS Y USUARIOS"
echo "============================================================"

echo
echo ">>> GET /routers/"
curl "$BASE/routers/"

echo
echo
echo ">>> GET /usuarios/"
curl "$BASE/usuarios/"

echo
echo "============================================================"
echo "FIN DEL SCRIPT - Topología y usuarios creados."
echo "============================================================"
