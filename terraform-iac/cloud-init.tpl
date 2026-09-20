#!/bin/bash
set -euxo pipefail

# Este script cuida SÓ de infraestrutura mínima do sistema operacional.
# Instalação de Docker, deploy do código e configuração da aplicação ficam
# a cargo do Ansible (separação entre provisionamento e configuração).

apt-get update

# Firewall do próprio SO — necessário mesmo com a Security List da OCI já
# liberando a porta, pois o Ubuntu Cloud Image vem com iptables restritivo.
apt-get install -y --no-install-recommends iptables-persistent
iptables -I INPUT -p tcp --dport ${app_port} -j ACCEPT
netfilter-persistent save
