#  MIT License
#
#  Copyright (c) 2025. Patrick Brammerloo, Mark Zijdemans, DirectVPS [https://directvps.nl/]
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
clusterid = settings.myclusterid
netboxtagopenstackapiscriptid = settings.netboxtagopenstackapiscriptid


def createnetboxvm(os_vm):
    try:
        # Create a Netbox VM based on passed values
        vm = nb.virtualization.virtual_machines.create(
            name=os_vm.name,
            status=os_vm.status,
            cluster=clusterid,
            vcpus=os_vm.flavorcpu,
            memory=os_vm.flavorram,
            tags=[netboxtagopenstackapiscriptid],
            custom_fields={'openstack_id': os_vm.instance_id, 'openstack_hypervisor': os_vm.hypervisor,
                           'openstack_flavor': os_vm.flavorname, 'openstack_swap': os_vm.flavorswap,
                           'openstack_ephemeral': os_vm.flavorephemeral, 'openstack_tenant': os_vm.tenant,
                           'openstack_hostname': os_vm.hostname},
            comments=f"Created by OpenStack API script but this time an Instance-based VM for {cluster_name}"
        )
        print(f"Created VM {os_vm.name} in Netbox cluster {cluster_name}.")
    except Exception as e:
        if ("The request failed with code 400 Bad Request:" in str(e) and
                "Virtual machine name must be unique per cluster." in str(e)):
            os_vm.name = os_vm.custom_name
            createnetboxvm(os_vm)
        else:
            print(f"Something went wrong when creating {os_vm.custom_name} in {cluster_name} \n{e}")
            sys.exit(1)


def createvmdisk(os_volume_object, netbox_vm):
    try:
        disker = nb.virtualization.virtual_disks.create(
            virtual_machine=netbox_vm.id,
            name=os_volume_object.vol_name,
            size=os_volume_object.vol_mb,
            comments=f"Created by OpenStack API script but this time its a Virtual Disk for {cluster_name}",
            tags=[netboxtagopenstackapiscriptid],
            custom_fields={'openstack_volumeid': os_volume_object.vol_id}
        )
        print(f"Created Volume {os_volume_object.vol_name} for {netbox_vm.name} ")
    except Exception as e:
        if ("The request failed with code 400 Bad Request:" in str(e) and
                "Virtual disk with this Virtual machine and Name already exists." in str(e)):
            os_volume_object.vol_name = os_volume_object.custom_name
            createvmdisk(os_volume_object, netbox_vm)
        else:
            print(f"Unable to create Volume {os_volume_object.vol_name} for {netbox_vm.name} \n{e}")
            sys.exit(1)


def createvminterface(os_interface_object, netbox_vm):
    try:
        interfacer = nb.virtualization.interfaces.create(
            virtual_machine=netbox_vm.id,
            name=os_interface_object.int_name,
            tags=[netboxtagopenstackapiscriptid],
            custom_fields={'openstack_interfaceid': os_interface_object.int_id}
        )
        print(f"Created interface {os_interface_object.int_name} for Virtual Machine {netbox_vm.name}")
    except Exception as e:
        if ("The request failed with code 400 Bad Request:" in str(e) and
                "Interface with this Virtual machine and Name already exists." in str(e)):
            os_interface_object.int_name = os_interface_object.custom_name
            createvminterface(os_interface_object, netbox_vm)
        else:
            print(f"Unable to create interface {os_interface_object.int_name} for Virtual Machine {netbox_vm.name} \n{e}")
            sys.exit(1)


def createnetboxmac(neutron_interface, netbox_interface):
    try:
        interfacemaccer = nb.dcim.mac_addresses.create(
            mac_address=neutron_interface['interfacemac'],
            assigned_object_id=netbox_interface.id,
            assigned_object_type="virtualization.vminterface",
            tags=[netboxtagopenstackapiscriptid],
            comments=f"Created by OpenStack API script but this time an Interface MAC-address for {cluster_name}"
        )
        print(f"Created NetBox MAC-address {neutron_interface['interfacemac']} "
              f"for Interface {netbox_interface.name} ID {netbox_interface.id}.")
        return interfacemaccer
    except Exception as e:
        print(f"Unable to create NetBox MAC-address {neutron_interface['interfacemac']} "
              f"for NetBox Interface ID {netbox_interface.id} and name {netbox_interface.name}. \n {e}")
        sys.exit(1)


def createnetboxvrf(myvrf, openstacknetworkid):
    vrfer = nb.ipam.vrfs.create(
        name=myvrf,
        comments=f"Created by OpenStack API script but this time a VRF for {cluster_name}",
        tags=[netboxtagopenstackapiscriptid],
        custom_fields={'openstack_networkid': openstacknetworkid}
    )


def createnetboxglobalsubnet(openstack_subnet_obj):
    try:
        subnetter = nb.ipam.prefixes.create(
            prefix=openstack_subnet_obj.cidr,
            status="active",
            comments=f"Created by OpenStack API script but this time a global subnet for {cluster_name}",
            tags=[netboxtagopenstackapiscriptid],
            custom_fields={'openstack_subnetid': openstack_subnet_obj.subnet_id}
        )
        print(f"Created global prefix {openstack_subnet_obj.cidr} for OpenStack subnet {openstack_subnet_obj.name} in the global VRF")
    except Exception as e:
        print(f"Unable to create NetBox global subnet based on OpenStack Subnet {openstack_subnet_obj.name} ID {openstack_subnet_obj.subnet_id} \n{e}")
        sys.exit(1)


def createnetboxprivatesubnet(openstack_subnet_obj, netbox_vrf):
    try:
        subnetter = nb.ipam.prefixes.create(
            prefix=openstack_subnet_obj.cidr,
            status="active",
            vrf=netbox_vrf.id,
            comments=f"Created by OpenStack API script but this time a private subnet for {cluster_name}",
            tags=[netboxtagopenstackapiscriptid],
            custom_fields={'openstack_subnetid': openstack_subnet_obj.subnet_id}
        )
        print(f"Created private prefix {openstack_subnet_obj.cidr} for {openstack_subnet_obj.name} in VRF {netbox_vrf.name}")
    except Exception as e:
        if ("The request failed with code 400 Bad Request:" in str(e) and
                "Duplicate prefix found in VRF" in str(e)):
            print(f"Error creating NetBox Prefix {openstack_subnet_obj.cidr} in VRF {netbox_vrf.name}. "
                  f"The Subnet already exists but its OpenStack ID does not match. Skipped it!")
            pass
        else:
            print(f"Unable to create NetBox private subnet based on OpenStack Subnet {openstack_subnet_obj.name} ID {openstack_subnet_obj.subnet_id} in VRF {netbox_vrf.name} \n{e}")
            sys.exit(1)


def createglobalipamip(address_object):
    # We create Netbox IP address on vm_name on interface 'interface'
    try:
        addresserwan = nb.ipam.ip_addresses.create(
            address=address_object.address,
            status=address_object.status,
            virtual_machine=address_object.nb_vm_id,
            interface=address_object.nb_int_id,
            comments=f"Created by OpenStack API script but this time a global IP-adress for {cluster_name}",
            assigned_object_type="virtualization.vminterface",
            assigned_object_id=address_object.nb_int_id,
            tags=[netboxtagopenstackapiscriptid]
        )
        print(f"Created WAN IP {address_object.address} for Netbox VM {address_object.nb_vm_name}, interface {address_object.nb_int_name}")
    except Exception as e:
        print(f"Unable to create WAN IP {address_object.address} for Netbox VM {address_object.nb_vm_name}, interface {address_object.nb_int_name} \n{e}")
        sys.exit(1)


def createlanipamip(address_object, netbox_vrf):
    try:
        addresserlan = nb.ipam.ip_addresses.create(
            address=address_object.address,
            status=address_object.status,
            virtual_machine=address_object.nb_vm_id,
            comments=f"Created by OpenStack API script but this time a private IP-adress for {cluster_name}",
            assigned_object_type="virtualization.vminterface",
            assigned_object_id=address_object.nb_int_id,
            vrf=netbox_vrf.id,
            tags=[netboxtagopenstackapiscriptid]
        )
        print(f"Created LAN IP {address_object.address} for Netbox VM {address_object.nb_vm_name}, interface {address_object.nb_int_name} in VRF {netbox_vrf.name}")
    except Exception as e:
        print("Unable to create LAN IP {address_obj.address} for Netbox VM {address_obj.nb_vm_name}, interface {address_obj.nb_int_name} in VRF {netbox_vrf.name} \n{e}")
        sys.exit(1)


def createnetboxrouter(name, status, routerid, tenantname):
    try:
        neutroner = nb.virtualization.virtual_machines.create(
            name=name,
            status=status,
            cluster=clusterid,
            tags=[netboxtagopenstackapiscriptid],
            custom_fields={'openstack_id': routerid, 'openstack_tenant': tenantname},
            comments=f"Created by OpenStack API script but this time a router-based VM for {cluster_name}"
        )
        print(f"Created router VM {name} in NetBox cluster {cluster_name}.")
    except Exception as e:
        print(f"Unable to create router VM {name} in NetBox cluster {cluster_name} \n{e}")
        sys.exit(1)


def createnetboxagent(name, agentid):
    try:
        neutronerdeux = nb.virtualization.virtual_machines.create(
            name=name,
            status="active",  # Assume the agent state is active
            cluster=clusterid,
            tags=[netboxtagopenstackapiscriptid],
            custom_fields={'openstack_id': agentid},
            comments=f"Created by OpenStack API script but this time a Neutron DHCP-agent based VM for {cluster_name}"
        )
        print(f"Created Neutron server {name} for DHCP-service ID {agentid} Netbox cluster {cluster_name}.")
    except Exception as e:
        print(f"Unable to create DHCP agent {name} fpr DHCP-service ID {agentid} in Netbox cluster {cluster_name} \n{e}")
        sys.exit(1)

