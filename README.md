
# Kolla Builder CLI

Kolla Builder is a command-line tool designed to automate the deployment and management of OpenStack environments using Kolla and Ansible.

## Features
- **Project Initialization**: Create new Kolla-based OpenStack projects with predefined templates.
- **Deployment**: Deploy OpenStack services on prepared nodes.
- **Node Management**: Spawn, prepare, and destroy virtual machines for OpenStack deployment.
- **Networking**: Manage networks for the deployment.
- **Remote Access**: SSH into deployed nodes for troubleshooting.
- **Service Installation**: Install NGINX on remote hosts.

## Dependencies
Ensure you have the following dependencies installed before using Kolla Builder:
- **Python 3**
- **Ansible** – Required for running deployment playbooks
- **PyYAML** – For handling configuration files
### These must be installed on remote server if you use remote server
- **lxml** – For XML parsing (install with `sudo pip install`)
- **Libvirt** – Required for managing virtual machines
- **QEMU/KVM** – Required for running VMs
- **Bridge-utils** – Helps with networking setup for virtual machines

On Debian/Ubuntu, install dependencies with:
```sh
sudo apt update && sudo apt install -y python3 ansible python3-yaml python3-lxml libvirt-daemon-system libvirt-clients qemu-kvm bridge-utils
```

On RHEL-based distributions:
```sh
sudo dnf install -y python3 ansible python3-pyyaml python3-lxml libvirt qemu-kvm bridge-utils
```

Make sure the `libvirtd` service is running:
```sh
sudo systemctl enable --now libvirtd
```

## Installation
Make the script executable and place it in a directory within your `$PATH`:
```sh
chmod +x kolla-builder.py
```

## Usage
Run the tool with the desired command:
```sh
./kolla-builder.py <command> [options]
```

### General Options
- `-i, --inventory <file>`: Specify an Ansible inventory file (default: `local`).

## Available Commands and Options

### 1. `init` – Initialize a New Kolla Project
```sh
./kolla-builder.py init <name> [options]
```
**Options:**
- `-b, --branch <branch>`: Specify a Git branch for the project (default: `master`).
- `-t, --template <file>`: Use a specific template file for the project.
- `-n, --nodes <file>`: Use a specific nodes template file.
- `-w, --network <file>`: Use a specific network template file.
- `-m, --master-only`: Use only the master template file without merging other templates.

### 2. `deploy` – Deploy OpenStack
```sh
./kolla-builder.py deploy <name> [options]
```


### 3. `spawn` – Create Virtual Machines
```sh
./kolla-builder.py spawn <name>
```
Creates VMs for the specified project using libvirt.

### 4. `prepare` – Prepare Nodes for Deployment
```sh
./kolla-builder.py prepare <name>
```
Runs Ansible playbooks to configure nodes before deploying OpenStack.

### 5. `destroy` – Remove Virtual Machines
```sh
./kolla-builder.py destroy <name> [options]
```
**Options:**
- `-d, --destroy-networks`: Remove associated networks as well.

### 6. `destroy-networks` – Remove Only Networks
```sh
./kolla-builder.py destroy-networks <name>
```
Deletes networks associated with the project.

### 7. `delete` – Completely Remove a Project
```sh
./kolla-builder.py delete <name> [options]
```
**Options:**
- `-d, --destroy-networks`: Also delete associated networks.
- **Warning**: This action is irreversible and requires confirmation.

### 8. `ssh` – Connect to a Node via SSH
```sh
./kolla-builder.py ssh <name>
```
Opens an SSH session to the deployment node.

### 9. `nginx` – Install NGINX on a Remote Host
```sh
./kolla-builder.py nginx <name>
```
Runs an Ansible playbook to install NGINX on the deployment node.

## Configuration
By default, Kolla Builder uses a configuration file (`builder-config.yaml`) with settings such as:
- User directories
- Template paths
- Playbook locations

Modify this file as needed before running the tool.

## Example Usage
Initialize a project with a custom network template:
```sh
./kolla-builder.py init my_project -w custom_network.yaml
```
Deploy OpenStack
```sh
./kolla-builder.py deploy my_project
```
Spawn VMs for the project:
```sh
./kolla-builder.py spawn my_project
```
Destroy a project and remove its networks:
```sh
./kolla-builder.py destroy my_project -d
```

