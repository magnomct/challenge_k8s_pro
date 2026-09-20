# Gera ansible/inventory.ini automaticamente com o IP público real da
# instância, assim que o Terraform termina de criá-la. Evita copiar/colar
# IP manualmente entre o output do Terraform e o Ansible.
resource "local_file" "ansible_inventory" {
  filename = "${path.module}/../ansible/inventory.ini"
  content = templatefile("${path.module}/inventory.tpl", {
    public_ip             = oci_core_instance.rag_agent.public_ip
    ssh_private_key_path  = var.ssh_private_key_path
  })
}
