# --- Credenciais da API da OCI (vêm da chave de API gerada no console) ---
variable "tenancy_ocid" {
  description = "OCID da tenancy (encontrado em Perfil > Tenancy no console OCI)"
  type        = string
}

variable "user_ocid" {
  description = "OCID do seu usuário (Perfil > User Settings)"
  type        = string
}

variable "fingerprint" {
  description = "Fingerprint da chave de API gerada em User Settings > API Keys"
  type        = string
}

variable "private_key_path" {
  description = "Caminho local para a chave privada .pem correspondente à API Key"
  type        = string
}

variable "region" {
  description = "Região da OCI, ex: sa-saopaulo-1"
  type        = string
  default     = "sa-saopaulo-1"
}

variable "compartment_ocid" {
  description = "OCID do compartimento onde os recursos serão criados"
  type        = string
}

# --- Acesso à instância ---
variable "ssh_public_key_path" {
  description = "Caminho local para sua chave pública SSH (ex: ~/.ssh/id_rsa.pub)"
  type        = string
}

variable "ssh_private_key_path" {
  description = "Caminho local para a chave privada SSH correspondente (usada pelo Ansible para conectar)"
  type        = string
}

# --- Dimensionamento da instância ---
variable "instance_shape" {
  description = "Shape da instância. VM.Standard.A1.Flex está no Always Free (ARM)."
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "instance_ocpus" {
  description = "Número de OCPUs (só se aplica a shapes Flex)"
  type        = number
  default     = 2
}

variable "instance_memory_gb" {
  description = "Memória em GB (só se aplica a shapes Flex)"
  type        = number
  default     = 12
}

# --- Rede ---
variable "vcn_cidr" {
  description = "Bloco CIDR da VCN"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "Bloco CIDR da subnet pública"
  type        = string
  default     = "10.0.1.0/24"
}

variable "app_port" {
  description = "Porta em que o Streamlit responde"
  type        = number
  default     = 8501
}

variable "allowed_ssh_cidr" {
  description = "CIDR liberado para SSH (restrinja ao seu IP em produção real, ex: 203.0.113.10/32)"
  type        = string
  default     = "0.0.0.0/0"
}

variable "allowed_app_cidr" {
  description = "CIDR liberado para acessar a aplicação web"
  type        = string
  default     = "0.0.0.0/0"
}
