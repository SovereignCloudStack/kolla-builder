#!/usr/bin/env python3

import argparse
import sys
import subprocess
import yaml
import os
import shutil
import ipaddress
from lxml import etree
default_config = {
    "user_directory": "./user",
    "template_directory":"./templates",
    "playbook_directory":".",
    "templates":{
        "nodes": "nodes/all-in-one.yaml",
        "network": "network/default.yaml",
        "master": "default.yaml",
    }
}


class KollaBuilder:
    def __init__(self,config, cfg_file="builder-config.yaml"):
        self.parser = argparse.ArgumentParser(description="Kolla Builder CLI")
        self.parser.add_argument("-i", "--inventory", help="Inventory, default local",default="local")

        self.subparsers = self.parser.add_subparsers(dest="command", required=True)

        deploy_parser = self.subparsers.add_parser("deploy", help="Deploy something")
        deploy_parser.add_argument("name", help="Name of the project")


        init_parser = self.subparsers.add_parser("init", help="Initialize a new project")
        init_parser.add_argument("name", help="Name of the project")
        init_parser.add_argument("-b", "--branch", help="Branch of the project, default 'master'", default="master")
        init_parser.add_argument("-t", "--template", default=None, help="Template file")
        init_parser.add_argument("-n", "--nodes", default=None, help="Template file ")
        init_parser.add_argument("-w", "--network", default=None, help="Template file")
        init_parser.add_argument("-m", "--master-only", action="store_true", help="Use master template file only, do not merge")

        spawn_parser = self.subparsers.add_parser("spawn", help="Spawn nodes to instal kolla on")

        spawn_parser.add_argument("name", help="Name of the project")

        destroy_parser = self.subparsers.add_parser("destroy", help="Delete nodes")

        destroy_parser.add_argument("name", help="Name of the project")
        destroy_parser.add_argument("-d", "--destroy-networks", action="store_true", help="Destroy networks as well")

        destroy_network_parser = self.subparsers.add_parser("destroy-networks", help="Delete nodes")

        destroy_network_parser.add_argument("name", help="Name of the project")

        delete_parser = self.subparsers.add_parser("delete", help="Delete nodes")

        delete_parser.add_argument("name", help="Name of the project")
        delete_parser.add_argument("-d", "--destroy-networks", action="store_true", help="Destroy networks as well")

        prepare_parser = self.subparsers.add_parser("prepare", help="Prepare nodes for kolla-deployment")

        prepare_parser.add_argument("name", help="Name of the project")

        ssh_parser = self.subparsers.add_parser("ssh", help="SSH into a node")

        ssh_parser.add_argument("name", help="Name of the project")

        nginx_parser = self.subparsers.add_parser("nginx", help="Install NGINX on remote host")

        nginx_parser.add_argument("name", help="Name of the project")

        self.args = self.parser.parse_args()
        self.config=config
        if cfg_file is not None:
            try:
                with open(cfg_file, "r") as f:
                    self.config = {**self.config,**yaml.safe_load(f)}
            except FileNotFoundError:
                print("Warning: config not found retrieving to default")

        self.ansible_commands = {
            **dict(
                spawn = self.spawn,
                prepare = self.prepare,
                deploy = self.deploy,
                destroy = self.destroy,
                nginx = self.nginx
            ),
            'destroy-networks': self.destroy_networks
        }
        self.project_commands = {
            **dict(
                init = self.init_project,
                ssh =  self.ssh,
                delete = self.delete
        ),
        **self.ansible_commands
        }
        self.commands = {
            **self.project_commands,
            **self.ansible_commands
        }
        if self.args.command in self.commands:
            if self.args.command in self.project_commands:
                self.project_path = self.project_path = f"{self.config['user_directory']}/{self.args.name}"
                if self.args.command != 'init':
                    with open(f"{self.project_path}/{self.args.name}.yml") as f:
                        self.node_config = yaml.safe_load(f)
    def run_or_ssh(self,cmd,**kwargs):
        host_info = self.get_host_info()
        ip = host_info[0]
        if ip != 'localhost':
            extract_prop={}
            for prop in host_info[1:]:
                k,v = tuple(prop.split('='))
                extract_prop[k]=v
            cmd = ['ssh',f"{extract_prop['ansible_ssh_user']}@{ip}", '-i',extract_prop['ansible_private_key_file'],'-o', 'IdentitiesOnly=yes','-t','bash -i -c "LIBVIRT_DEFAULT_URI=qemu:///system ' + " ".join(cmd)+'"' ]
        return subprocess.run(cmd,**kwargs)

    def get_host_info(self):
        with open(self.args.inventory) as f:
            for line in f.readlines():
                if '[' not in line:
                    return line.split()
            else:
                raise

    def get_network_exists(self,network_name):
        try:
            self.run_or_ssh(["virsh", "net-info", network_name], capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            return False

    def get_network_max_ip(self,network_name):
        result = self.run_or_ssh(["virsh", "net-dumpxml", network_name], capture_output=True, text=True, check=True)
        xml=result.stdout[result.stdout.find("<"):]
        root = etree.fromstring(xml)
        dhcp_element = root.xpath("//ip/dhcp")
        if not dhcp_element:
            print("No DHCP configuration found.")
            raise
        max_ip=None
        for host in dhcp_element[0].xpath("host"):
            ip_obj = ipaddress.IPv4Address(host.get('ip'))
            if max_ip is None or ip_obj > max_ip:
                max_ip = ip_obj
        return str(max_ip)


    def get_node_property(self, var, default=None, strict=False):
        if self.node_config is None:
            print("Project not loaded")
            raise
        try:
            return self.node_config[var]
        except KeyError:
            if strict:
                raise
            return default

    def get_deploy_node(self):
        is_aio = self.get_node_property("is_aio",True)
        if is_aio:
            deploy_node = self.args.name
        else:
            nodes = self.get_node_property("nodes",strict=True)
            for node in nodes:
                try:
                    dep = node["deployment"]
                except KeyError:
                    dep = False
                if dep:
                    deploy_node = node['name']
                    break
            else:
                raise
        return deploy_node

    def deploy(self):
        if self.project_get_state() >= 2:
            ssh_config = self.get_node_property("ssh_config",f"{self.project_path}/ssh_config")
            deploy_node = self.get_deploy_node()
            command = ["ssh", "-F", ssh_config,"-t",deploy_node,'bash -i -c "./deploy"' ]
            subprocess.run(command, check=True)
            self.project_update_state(3)
        else:
            print(f"Project {self.args.name} not prepared, preparing")
            self.prepare()
            print(f"Project {self.args.name} prepared sucesfully, calling 'deploy' again")
            self.deploy()

    def ansible_playbook(self, playbook, extra_vars, inventory=None, vm_list=None):
        playbook=f"{self.config['playbook_directory']}/{playbook}"
        if inventory is None:
            inventory = self.args.inventory
        if vm_list is None:
            command = ["ansible-playbook","-i", inventory, "-e", f"@{extra_vars}", playbook]
        else:
            command = ["ansible-playbook", "-i", inventory, "-e", f"@{extra_vars}", "-e", f"@{vm_list}", playbook]
        subprocess.run(command, check=True)

    def init_project(self):
        template_path = f"{self.config['template_directory']}"
        if self.args.template is None:
            self.args.template = self.config['templates']['master']
        if not self.args.master_only:
            if self.args.nodes is None:
                self.args.nodes = self.config['templates']['nodes']
            if self.args.network is None:
                self.args.network = self.config['templates']['network']
        if not os.path.isdir(self.project_path):
            with open (f"{template_path}/{self.args.template}") as f:
                master = yaml.safe_load(f)
            if not self.args.master_only:
                with open (f"{template_path}/{self.args.nodes}") as f:
                    nodes = yaml.safe_load(f)
                with open (f"{template_path}/{self.args.network}") as f:
                    network = yaml.safe_load(f)
                master = {**network,**nodes,**master}
            master['inventory_name']=self.args.name
            master['globals_file']=f"{self.project_path}/globals.yml"
            master['git_branch']=self.args.branch
            if master["is_aio"]:
                master["node_name"]=self.args.name
                master['aio_filepath']=f"{self.project_path}/{self.args.name}"
            else:
                master['multinode_file_path']=f"{self.project_path}/{self.args.name}"
                for i,node in enumerate(master["nodes"]):
                    master["nodes"][i]["name"]=f'{self.args.name}-{node["name"]}'
                master["vm_list_path"]=f"{self.project_path}/vm_list.yaml"
            os.mkdir(self.project_path)
            ip = self.get_host_info()[0]
            if ip == 'localhost':
                master['is_remote'] = False
            else:
                master['is_remote'] = True
            master['create_network_ssh'] = not self.get_network_exists(master['network_ssh'])
            master['create_network_openstack'] = not self.get_network_exists(master['network_openstack'])
            master['create_network_neutron'] = not self.get_network_exists(master['network_neutron'])
            if self.get_network_exists(master['network_ssh']):
                master['network_ssh_ip'] = self.get_network_max_ip(master['network_ssh'])

            if not 'ssh_config' in master:
                master['ssh_config']=f'{self.project_path}/ssh_config'
                with open(f'{self.project_path}/ssh_config','w') as ff:
                    pass
            with open(f'{self.project_path}/{self.args.name}.yml','w') as ff:
                yaml.safe_dump(master,ff)

        with open(f"{self.project_path}/.kolla-project-info","w") as f:
            yaml.safe_dump(dict(name=self.args.name,state=0),f)
        with open(f"{self.project_path}/globals.yml","w") as f:
            # HACK: Kolla ansible does not accept empty files in globals.d
            yaml.safe_dump(dict(kolla_dev_mode="no"),f)

    def project_update_state(self,state):
        project_path = f"{self.config['user_directory']}/{self.args.name}"
        with open(f"{self.project_path}/.kolla-project-info") as f:
            obj=yaml.safe_load(f)
        obj['state']=state
        with open(f"{self.project_path}/.kolla-project-info",'w') as f:
            yaml.safe_dump(obj,f)

    def project_get_state(self):
        project_path = f"{self.config['user_directory']}/{self.args.name}"
        obj={}
        with open(f"{project_path}/.kolla-project-info") as f:
            obj=yaml.safe_load(f)
        return int(obj['state'])

    def spawn(self):
        if self.project_get_state()==0:
            project_path=f"{self.config['user_directory']}/{self.args.name}"
            self.ansible_playbook("spawn.yml",f"{self.project_path}/{self.args.name}.yml")
            self.project_update_state(1)
        else:
            print(f"Project {self.args.name} is already spawned")

    def destroy(self):
        if self.get_node_property("is_aio",strict=True):
            self.ansible_playbook("destroy.yml",f"{self.project_path}/{self.args.name}.yml")
        else:
            vm_list = self.get_node_property("vm_list_path",strict=True)
            self.ansible_playbook("destroy.yml",f"{self.project_path}/{self.args.name}.yml",vm_list=vm_list)
        if self.args.destroy_networks:
            self.destroy_networks()
        self.project_update_state(0)

    def nginx(self):
        if self.project_get_state() >=3:
            self.ansible_playbook("nginx.yml",f"{self.project_path}/{self.args.name}.yml")
    def destroy_networks(self):
        self.ansible_playbook("destroy-networks.yml",f"{self.project_path}/{self.args.name}.yml")
    def delete(self):
        if input("Type yes to confirm: ") != "yes":
            return
        if self.project_get_state()>0:
            self.destroy()
        shutil.rmtree(self.project_path)
    def prepare(self):
        if self.project_get_state() > 0:
            inventory=f"{self.project_path}/{self.args.name}"
            self.ansible_playbook("prepare.yml",f"{self.project_path}/{self.args.name}.yml",inventory=inventory)
            self.project_update_state(2)
        else:
            print(f"Project {self.args.name} not spawned, spawning")
            self.spawn()
            print(f"Project {self.args.name} spawned sucesfully, calling 'prepare' again")
            self.prepare()

    def ssh(self):
        ssh_config = self.get_node_property("ssh_config",f"{self.project_path}/ssh_config")
        deploy_node = self.get_deploy_node()
        command = ["ssh", "-F", ssh_config,"-t",deploy_node ]
        subprocess.run(command, check=True)

    def run(self):
        if self.args.command in self.commands:
            self.commands[self.args.command]()
        else:
            raise

if __name__ == "__main__":
    KollaBuilder(default_config).run()
    # print(KollaBuilder(default_config).get_network_max_ip('kolla-ssh'))
