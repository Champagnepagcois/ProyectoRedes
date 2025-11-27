#!/bin/bash
# ==========================================================
# Script: test_api_redes_full.sh
# Objetivo: poblar la BD y probar TODA la arquitectura
# Requisitos:
#   - API corriendo en http://localhost:8000
#   - curl instalado
#   - jq instalado (opcional, solo para pretty-print)
# Nota:
#   Ajusta hostnames / IPs si tu topología REAL es diferente.
#   Aquí se asume:
#     Edge  -> 192.168.100.1
#     R1    -> 192.168.100.2
#     R2    -> 192.168.100.3
#     TOR1  -> 192.168.100.4
#     TOR2  -> 192.168.100.5
#     TOR3  -> 192.168.100.6
# ==========================================================

BASE="http://localhost:8000"

sep() {
  echo
  echo "============================================================"
  echo ">>> $1"
  echo "============================================================"
  echo
}

# ------------------------------------------------------------------
# 1. CREAR TODOS LOS ROUTERS CON SUS INTERFACES
# ------------------------------------------------------------------

sep "1) Creando routers e interfaces (Edge, R1, R2, TOR1, TOR2, TOR3)"

# EDGE
curl -s -X POST "$BASE/routers/" \
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
      "name": "f1_0",
      "ip_address": "10.0.0.1",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "R1"
    },
    {
      "name": "f1_1",
      "ip_address": "10.0.0.5",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "R2"
    }
  ]
}' | jq . || echo

# R1
curl -s -X POST "$BASE/routers/" \
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
      "name": "f1_0",
      "ip_address": "10.0.0.2",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "Edge"
    },
    {
      "name": "f1_1",
      "ip_address": "10.0.0.9",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "TOR1"
    },
    {
      "name": "f1_2",
      "ip_address": "10.0.0.13",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "TOR2"
    }
  ]
}' | jq . || echo

# R2
curl -s -X POST "$BASE/routers/" \
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
      "name": "f1_0",
      "ip_address": "10.0.0.6",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "Edge"
    },
    {
      "name": "f1_1",
      "ip_address": "10.0.0.17",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "TOR3"
    }
  ]
}' | jq . || echo

# TOR1
curl -s -X POST "$BASE/routers/" \
-H "Content-Type: application/json" \
-d '{
  "hostname": "TOR1",
  "ip_admin": "192.168.100.4",
  "loopback": "192.168.50.4",
  "role": "leaf",
  "vendor": "Cisco",
  "os_version": "IOS 15",
  "interfaces": [
    {
      "name": "f1_0",
      "ip_address": "10.0.0.10",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "R1"
    }
  ]
}' | jq . || echo

# TOR2
curl -s -X POST "$BASE/routers/" \
-H "Content-Type: application/json" \
-d '{
  "hostname": "TOR2",
  "ip_admin": "192.168.100.5",
  "loopback": "192.168.50.5",
  "role": "leaf",
  "vendor": "Cisco",
  "os_version": "IOS 15",
  "interfaces": [
    {
      "name": "f1_0",
      "ip_address": "10.0.0.14",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "R1"
    }
  ]
}' | jq . || echo

# TOR3
curl -s -X POST "$BASE/routers/" \
-H "Content-Type: application/json" \
-d '{
  "hostname": "TOR3",
  "ip_admin": "192.168.100.6",
  "loopback": "192.168.50.6",
  "role": "leaf",
  "vendor": "Cisco",
  "os_version": "IOS 15",
  "interfaces": [
    {
      "name": "f1_0",
      "ip_address": "10.0.0.18",
      "mask": "255.255.255.252",
      "status": "up",
      "protocol": "up",
      "neighbor_hostname": "R2"
    }
  ]
}' | jq . || echo

# ------------------------------------------------------------------
# 2. CONSULTAS BÁSICAS DE ROUTERS E INTERFACES
# ------------------------------------------------------------------

sep "2) Listar routers e interfaces por router"

echo ">>> GET /routers/"
curl -s "$BASE/routers/" | jq . || echo

for R in Edge R1 R2 TOR1 TOR2 TOR3; do
  echo
  echo ">>> Detalle del router $R"
  curl -s "$BASE/routers/$R" | jq . || echo

  echo
  echo ">>> Interfaces de $R"
  curl -s "$BASE/routers/$R/interfaces" | jq . || echo
done

# ------------------------------------------------------------------
# 3. CRUD DE USUARIOS GLOBALES
# ------------------------------------------------------------------

sep "3) CRUD de usuarios globales"

echo ">>> Crear usuario global 'operador'"
curl -s -X POST "$BASE/usuarios/" \
-H "Content-Type: application/json" \
-d '{"username":"operador","privilege":5,"permissions":"read-only"}' | jq . || echo

echo ">>> Crear usuario global 'netadmin'"
curl -s -X POST "$BASE/usuarios/" \
-H "Content-Type: application/json" \
-d '{"username":"netadmin","privilege":15,"permissions":"full"}' | jq . || echo

echo ">>> Listar usuarios globales"
curl -s "$BASE/usuarios/" | jq . || echo

echo ">>> Actualizar usuario global operador (privilege=7)"
curl -s -X PUT "$BASE/usuarios/operador" \
-H "Content-Type: application/json" \
-d '{"privilege":7}' | jq . || echo

# ------------------------------------------------------------------
# 4. CRUD DE USUARIOS POR ROUTER
# ------------------------------------------------------------------

sep "4) CRUD de usuarios por router"

echo ">>> Crear usuario 'soporte' en R1"
curl -s -X POST "$BASE/routers/R1/usuarios/" \
-H "Content-Type: application/json" \
-d '{"username":"soporte","privilege":5,"permissions":"troubleshoot"}' | jq . || echo

echo ">>> Crear usuario 'soporte' en Edge"
curl -s -X POST "$BASE/routers/Edge/usuarios/" \
-H "Content-Type: application/json" \
-d '{"username":"soporte","privilege":5,"permissions":"troubleshoot"}' | jq . || echo

echo ">>> Listar usuarios en cada router"
for R in Edge R1 R2 TOR1 TOR2 TOR3; do
  echo
  echo "Router $R - usuarios:"
  curl -s "$BASE/routers/$R/usuarios/" | jq . || echo
done

echo ">>> Actualizar usuario 'soporte' en R1 (privilege=10)"
curl -s -X PUT "$BASE/routers/R1/usuarios/soporte" \
-H "Content-Type: application/json" \
-d '{"privilege":10}' | jq . || echo

echo ">>> Eliminar usuario 'soporte' en Edge"
curl -s -X DELETE "$BASE/routers/Edge/usuarios/soporte" | jq . || echo

# ------------------------------------------------------------------
# 5. TOPOLOGÍA Y DEMONIO
# ------------------------------------------------------------------

sep "5) Topología y demonio /topologia"

echo ">>> GET /topologia"
curl -s "$BASE/topologia" | jq . || echo

echo ">>> POST /topologia (activar demonio lógico)"
curl -s -X POST "$BASE/topologia" | jq . || echo

echo ">>> PUT /topologia (cambiar intervalo a 120s)"
curl -s -X PUT "$BASE/topologia" \
-H "Content-Type: application/json" \
-d '{"interval_seconds":120}' | jq . || echo

echo ">>> GET /topologia/grafica -> topo.png"
curl -s "$BASE/topologia/grafica" -o topo.png
echo "Imagen de topología guardada como topo.png"

echo ">>> DELETE /topologia (detener demonio)"
curl -s -X DELETE "$BASE/topologia" | jq . || echo

# ------------------------------------------------------------------
# 6. SNMP TEST Y ESTADO DE ROUTERS
# ------------------------------------------------------------------

sep "6) SNMP test y /routers/<hostname>/estado"

echo ">>> Probar SNMP básico (sysName/sysUpTime) contra R1 (ip_admin 192.168.100.2)"
curl -s -X POST "$BASE/snmp/test" \
-H "Content-Type: application/json" \
-d '{"host":"192.168.100.2"}' | jq . || echo

echo ">>> Estado SNMP de todos los routers registrados en la BD"
for R in Edge R1 R2 TOR1 TOR2 TOR3; do
  echo
  echo "Router $R:"
  curl -s "$BASE/routers/$R/estado" | jq . || echo
done

# ------------------------------------------------------------------
# 7. SSH TEST
# ------------------------------------------------------------------

sep "7) Probar SSH /ssh/test (show ip interface brief) a Edge"

curl -s -X POST "$BASE/ssh/test" \
-H "Content-Type: application/json" \
-d '{"host":"192.168.100.1","command":"show ip interface brief"}' | jq . || echo

# ------------------------------------------------------------------
# 8. MONITOREO DE OCTETOS Y GRÁFICA
# ------------------------------------------------------------------

sep "8) Monitoreo de octetos en interfaz ifIndex=1 de R1"

echo ">>> POST /routers/R1/interfaces/1/octetos/10 (iniciar y guardar monitoreo de 10s)"
curl -s -X POST "$BASE/routers/R1/interfaces/1/octetos/10" | jq . || echo

echo ">>> GET /routers/R1/interfaces/1/octetos/10 (recuperar datos almacenados)"
curl -s "$BASE/routers/R1/interfaces/1/octetos/10" | jq . || echo

echo ">>> GET /routers/R1/interfaces/1/grafica?segundos=10 -> grafica_r1_if1.png"
curl -s "$BASE/routers/R1/interfaces/1/grafica?segundos=10" -o grafica_r1_if1.png
echo "Imagen de monitoreo guardada como grafica_r1_if1.png"

echo ">>> DELETE /routers/R1/interfaces/1/octetos/10 (borrar monitoreo en memoria)"
curl -s -X DELETE "$BASE/routers/R1/interfaces/1/octetos/10" | jq . || echo

# ------------------------------------------------------------------
# 9. TRAPS LINKUP/LINKDOWN
# ------------------------------------------------------------------

sep "9) Trampas linkup/linkdown en interfaz ifIndex=1 de R1"

echo ">>> GET /estado interfaz (sin traps aún)"
curl -s "$BASE/routers/R1/interfaces/1/estado" | jq . || echo

echo ">>> POST /estado (activar captura de trampas)"
curl -s -X POST "$BASE/routers/R1/interfaces/1/estado" | jq . || echo

echo ">>> GET /estado (consultar eventos registrados hasta ahora)"
curl -s "$BASE/routers/R1/interfaces/1/estado" | jq . || echo

echo ">>> DELETE /estado (detener captura de trampas)"
curl -s -X DELETE "$BASE/routers/R1/interfaces/1/estado" | jq . || echo

# ------------------------------------------------------------------
# 10. FIN
# ------------------------------------------------------------------

sep "FIN DEL SCRIPT - Revisa los JSON en consola y las imágenes topo.png / grafica_r1_if1.png"

exit 0
