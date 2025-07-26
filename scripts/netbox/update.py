#  MIT License
#
#  Copyright (c) 2024. Patrick Brammerloo, Mark Zijdemans, DirectVPS [https://directvps.nl/]
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.

import sys

import settings
nb = settings.nb
cluster_name = settings.cluster_name
netboxtagopenstackapiscriptid = settings.netboxtagopenstackapiscriptid


def updatenetboxvm(netbox_vm_id, os_vm):
    # Update OpenStack VM in Netbox based on given values
    # Any value passed to Netbox API, will only do something if the value is different
    try:
        vmer = nb.virtualization.virtual_machines.update([
            {'id': netbox_vm_id,
             'name': os_vm.name,
             'status': os_vm.status,
             'vcpus': os_vm.flavorcpu,
             'memory': os_vm.flavorram,
             'custom_fields': {'openstack_id': os_vm.instance_id, 'openstack_hypervisor': os_vm.hypervisor,
                               'openstack_flavor': os_vm.flavorname, 'openstack_swap': os_vm.flavorswap,
                               'openstack_ephemeral': os_vm.flavorephemeral, 'openstack_tenant': os_vm.tenant,
                               'openstack_hostname': os_vm.hostname}
             }
        ])
        print(f"Updated {os_vm.name} in Netbox cluster {cluster_name} based on OpenStack ID {os_vm.instance_id}")
    except Exception as e:
        if ("The request failed with code 400 Bad Request:" in str(e) and
                "Virtual machine name must be unique per cluster." in str(e)):
            # If the VM in OpenStack still does not have a unique name for us to use in NetBox
            # We update it with our custom name instead
            os_vm.name = os_vm.custom_name
            updatenetboxvm(netbox_vm_id, os_vm)
            print(f"Updated custom-named VM {os_vm.custom_name} in Netbox cluster {cluster_name} "
                  f"based on OpenStack ID {os_vm.instance_id}")
        else:
            print(f"Unable to update custom-named VM {os_vm.customname} in Netbox cluster {cluster_name} "
                  f"based on OpenStack ID {os_vm.instance_id} \n{e}")
            sys.exit(1)


def updatevmdisk(openstack_volume_obj, netbox_vm, netbox_vol):
    try:
        disker = nb.virtualization.virtual_disks.update([
            {"id": netbox_vol.id,
             "virtual_machine": netbox_vm.id,
             "name": openstack_volume_obj.vol_name,
             "size": openstack_volume_obj.vol_mb
             }
        ])
        print(f"Updated Volume {openstack_volume_obj.vol_name} for VM "
              f"{netbox_vm.name} because ID {openstack_volume_obj.vol_id} was found")
    except Exception as e:
        if ("The request failed with code 400 Bad Request:" in str(e) and
                "Virtual disk with this Virtual machine and Name already exists." in str(e)):
            openstack_volume_obj.vol_name = openstack_volume_obj.custom_name
            updatevmdisk(openstack_volume_obj, netbox_vm, netbox_vol)
        else:
            print(f"Unable to update Volume {openstack_volume_obj.vol_name} for {netbox_vm.name} \n{e}")
            sys.exit(1)


def updatevminterface(openstack_interface_obj, netbox_int, netbox_vm):
    try:
        interfacer = nb.virtualization.interfaces.update([
            {'id': netbox_int.id,
             'virtual_machine': netbox_vm.id,
             'name': openstack_interface_obj.int_name
             }
        ])
        print(f"Updated Interface {openstack_interface_obj.int_name} for VM "
              f"{netbox_vm.name} because ID {openstack_interface_obj.int_id} was found")
    except Exception as e:
        if ("The request failed with code 400 Bad Request:" in str(e) and
                "Interface with this Virtual machine and Name already exists." in str(e)):
            openstack_interface_obj.int_name = openstack_interface_obj.custom_name
            updatevminterface(openstack_interface_obj, netbox_int, netbox_vm)
        else:
            print(f"Unable to update Interface {openstack_interface_obj.int_name} VM {netbox_vm.name} \n{e}")
            sys.exit(1)


def update_netbox_interface_mac(netbox_mac_address, netbox_interface):
    try:
        interfacer = nb.virtualization.interfaces.update([
            {'id': netbox_interface.id,
             'primary_mac_address': netbox_mac_address.id,
             }
        ])
        print(f"Set MAC-address {netbox_mac_address.mac_address} as primary for "
              f"Interface {netbox_interface.name} ID Interface {netbox_interface.id}.")
    except Exception as e:
        print(f"Unable to set MAC-address {netbox_mac_address.mac_address} as primary"
              f" for Interface {netbox_interface.name} \n{e}")
        # It's not worth exiting the script for
        # sys.exit(1)


def updatenetboxvrf(osvrfname, nbvrfid):
    vrfer = nb.ipam.vrfs.update([
        {"name": osvrfname,
         "id": nbvrfid
         }
    ])


def updatenetboxglobalsubnet(openstack_subnet_obj, netbox_prefix):
    try:
        subnetter = nb.ipam.prefixes.update([
            # We already found the prefix in NetBox, so all we're doing is adding the OpenStack subnet ID to it
            {"id": netbox_prefix.id,
             "custom_fields": {'openstack_subnetid': openstack_subnet_obj.subnet_id}
             }
        ])
        print(f"Updated global prefix {netbox_prefix.prefix} by adding "
              f"OpenStack Subnet ID {openstack_subnet_obj.subnet_id}")
    except Exception as e:
        print(f"Unable to update global prefix {netbox_prefix.prefix} based on "
              f"OpenStack Subnet {openstack_subnet_obj.name} ID {openstack_subnet_obj.subnet_id} \n{e}")
        sys.exit(1)


def updatenetboxsubnet(openstack_subnet_obj, netbox_prefix):
    try:
        subnetter = nb.ipam.prefixes.update([
            {"prefix": openstack_subnet_obj.cidr,
             "id": netbox_prefix.id
             }
        ])
        print(f'Updated prefix {netbox_prefix.prefix} based on '
              f'OpenStack network {openstack_subnet_obj.name} CIDR {openstack_subnet_obj.cidr}')
    except Exception as e:
        print(f"Unabled to update prefix {netbox_prefix.prefix} based on "
              f"OpenStack Subnet {openstack_subnet_obj.name} ID {openstack_subnet_obj.subnet_id} \n{e}")
        sys.exit(1)


def updateglobalipamip(address_object, nb_ip):
    try:
        addresserglobal = nb.ipam.ip_addresses.update([
            {"id": nb_ip.id,
             "status": address_object.status,
             "assigned_object_type": "virtualization.vminterface",
             "assigned_object_id": address_object.nb_int_id
             }
        ])
        print(f"Updated WAN IP {nb_ip.address} to VM {address_object.nb_vm_name} "
              f"Interface {address_object.nb_int_name}, in the Global VRF")
    except Exception as e:
        print(f"Unable to update WAN IP {nb_ip.address} for Netbox VM {address_object.nb_vm_name} "
              f"Interface {address_object.nb_int_name}, in the Global VRF \n{e}")
        sys.exit(1)


def updatelanipamip(address_object, nb_ip):
    try:
        addresserprivate = nb.ipam.ip_addresses.update([
            {"id": nb_ip.id,
             "status": address_object.status,
             "assigned_object_type": "virtualization.vminterface",
             "assigned_object_id": address_object.nb_int_id
             }
        ])
        print(f"Updated LAN IP {nb_ip.address} to VM {address_object.nb_vm_name}, "
              f"interface {address_object.nb_int_name}")
    except Exception as e:
        print(f"Unable to update LAN IP {nb_ip.address} for Netbox VM {address_object.nb_vm_name}, "
              f"interface {address_object.nb_int_name} \n{e}")
        sys.exit(1)


def updatenetboxrouter(netbox_vm_id, name, status):
    try:
        routerer = nb.virtualization.virtual_machines.update([
            {'id': netbox_vm_id,
             'name': name,
             'status': status
             }
        ])
        print(f"Updated router {name} in NetBox cluster {cluster_name}, for VM {netbox_vm_id}")
    except Exception as e:
        print(f"Unable to update router {name} in NetBox cluster {cluster_name} for VM {netbox_vm_id} \n{e}")
        sys.exit(1)


def updatenetboxagent(netbox_vm_id, name):
    try:
        agenter = nb.virtualization.virtual_machines.update([
            {'id': netbox_vm_id,
             'name': name
             }
        ])
        print(f"Updated Neutron server {name} in Netbox cluster {cluster_name}, because its DHCP-service ID was found")
    except Exception as e:
        print(f"Unable to update Neutron server {name} in Netbox cluster {cluster_name} \n{e}")
        sys.exit(1)
