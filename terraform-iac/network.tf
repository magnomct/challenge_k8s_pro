# --- VCN (rede virtual isolada para este projeto) ---
resource "oci_core_vcn" "rag_agent_vcn" {
  compartment_id = var.compartment_ocid
  cidr_block     = var.vcn_cidr
  display_name   = "rag-agent-vcn"
  dns_label      = "ragagent"
}

# --- Internet Gateway: necessário para a instância ter IP público ---
resource "oci_core_internet_gateway" "rag_agent_igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.rag_agent_vcn.id
  display_name   = "rag-agent-igw"
  enabled        = true
}

# --- Tabela de rotas: tudo que não é interno da VCN sai pela internet ---
resource "oci_core_route_table" "rag_agent_rt" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.rag_agent_vcn.id
  display_name   = "rag-agent-route-table"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.rag_agent_igw.id
  }
}

# --- Security List: equivalente a um firewall stateful na borda da subnet ---
resource "oci_core_security_list" "rag_agent_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.rag_agent_vcn.id
  display_name   = "rag-agent-security-list"

  # SSH — restrinja allowed_ssh_cidr ao seu IP em um ambiente real de produção
  ingress_security_rules {
    protocol = "6" # TCP
    source   = var.allowed_ssh_cidr
    tcp_options {
      min = 22
      max = 22
    }
  }

  # Streamlit
  ingress_security_rules {
    protocol = "6"
    source   = var.allowed_app_cidr
    tcp_options {
      min = var.app_port
      max = var.app_port
    }
  }

  # Note: a porta do Postgres (5432) NÃO é liberada aqui de propósito — o
  # banco só é acessível de dentro da rede interna do docker-compose,
  # nunca pela rede da VCN nem pela internet.

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }
}

# --- Subnet pública onde a instância vai viver ---
resource "oci_core_subnet" "rag_agent_subnet" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.rag_agent_vcn.id
  cidr_block                 = var.subnet_cidr
  display_name               = "rag-agent-subnet"
  dns_label                  = "ragsubnet"
  route_table_id             = oci_core_route_table.rag_agent_rt.id
  security_list_ids          = [oci_core_security_list.rag_agent_sl.id]
  prohibit_public_ip_on_vnic = false
}
