#!/bin/bash

# Function to display help
show_help() {
    echo "Usage: $0 [options] action extravars [ansible-playbook options]"
    echo ""
    echo "Options:"
    echo "  -r                  Use -i remote (default is -i local, ignored if action is 'prepare')"
    echo "  -h                  Display this help message"
    echo ""
    echo "Actions:"
    echo "  ara, spawn, prepare, delete, nginx"
    echo ""
    echo "Example:"
    echo "  $0 -r spawn extravars.yml -v"
}
# Default inventory file
inventory="local"

# Parse options
while getopts ":rh" opt; do
    case ${opt} in
        r )
            inventory="remote"
            ;;
        h )
            show_help
            exit 0
            ;;
        \? )
            echo "Invalid option: -${OPTARG}" >&2
            show_help
            exit 1
            ;;
        : )
            echo "Option -${OPTARG} requires an argument." >&2
            show_help
            exit 1
            ;;
    esac
done
shift $((OPTIND -1))

# Check if the action and user_variables are provided
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Error: both action and user_variables are required."
    show_help
    exit 1
fi

action=$1
user_variables=$2
shift 2

# Strip .yml from the action if present
action=${action%.yml}

# Validate the action
valid_actions=("ara" "spawn" "prepare" "delete" "nginx")
if [[ ! " ${valid_actions[@]} " =~ " ${action} " ]]; then
    echo "Error: invalid action. Valid actions are: ara, spawn, prepare, delete, nginx."
    show_help
    exit 1
fi
vmlist=""

if [ "$action" == "prepare" ]; then
    kolla_inventory=$(grep "inventory_name:" $user_variables | cut -d" " -f2 | sed 's/"//g')
    if [ -z "${kolla_inventory}" ]; then
        inventory="kolla-inventory"
    else
        inventory="${kolla_inventory}"
    fi


elif [ "$action" == "delete" ]; then
    vmlist="-e @vm_list.yml"

elif [ "$action" == "nginx" ]; then
    inventory="remote"
fi

cmd="ansible-playbook -i $inventory $action.yml -e @$user_variables $vmlist"

# Add any remaining arguments
cmd="$cmd $@"

# Execute the ansible-playbook command
echo "Executing: $cmd"
$cmd
