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
import os
import time
import ipaddress

sys.path.insert(1, os.path.join(sys.path[0], '..'))
import settings
nb = settings.nb
cluster_name = settings.cluster_name

from openstack.fetchinfo import get_nova
from openstack.fetchinfo import get_cinder
from openstack.fetchinfo import get_neutron


def get_netbox_vms():
    # VMs
    nb_vms_cluster = nb.virtualization.virtual_machines.filter(tag="openstack-api-script", cluster=cluster_name)
    netbox_vm_dic_openstack = {}
    netbox_vm_dic_netbox = {}
    for nbvm in nb_vms_cluster:
        # We filter for all VMs in our NetBox cluster
        netbox_vm_dic_openstack[nbvm.custom_fields["openstack_id"]] = nbvm  # OS keys!
        netbox_vm_dic_netbox[nbvm.id] = nbvm  # NB keys!
    print(f"Fetched and built VM dictionaries")
    return netbox_vm_dic_openstack, netbox_vm_dic_netbox


def get_netbox_interfaces(nb_vm_dic):
    # Interfaces
    nb_interfaces_total = nb.virtualization.interfaces.filter(tag="openstack-api-script")
    netbox_int_dic_openstack = {}
    netbox_int_dic_netbox = {}
    for nbinterface in nb_interfaces_total:
        if nbinterface.virtual_machine.id in nb_vm_dic.keys():
            # We filter for Interfaces assigned to VMs in our cluster
            netbox_int_dic_openstack[nbinterface.custom_fields["openstack_interfaceid"]] = nbinterface
            netbox_int_dic_netbox[nbinterface.id] = nbinterface
        else:
            pass
    print(f"Fetched and built Interface dictionaries")
    return netbox_int_dic_openstack, netbox_int_dic_netbox


def get_netbox_addresses(netbox_int_dic):
    # Addresses
    nb_openstack_addresses = nb.ipam.ip_addresses.filter(tag="openstack-api-script")
    # Addresses may not have the tag, in case of WAN IPs
    netbox_addr_dic_netbox = {}
    for address in nb_openstack_addresses:
        # We filter for Addresses assigned to Interfaces assigned to VMs in our cluster
        if address.assigned_object.id in netbox_int_dic.keys():
            netbox_addr_dic_netbox[address.id] = address
        else:
            continue
    print(f"Fetched and built Address dictionaries")
    return netbox_addr_dic_netbox


def get_netbox_vrfs(netbox_addr_dic):
    # VRFs
    netboxvrfs = nb.ipam.vrfs.all()  # Although all our VRFs have the Tag, we make sure we only pick the right ones
    netbox_vrf_dic_all = {}
    netbox_vrf_dic_filtered_netbox = {}  # We use this to filter for prefixes later
    netbox_vrf_dic_openstack = {}
    netbox_vrf_dic_netbox = {}
    for nbvrf in netboxvrfs:
        # First we collect all VRFs in existence
        # Keep in mind the script doesn't create VRFs for global addresses/prefixes
        netbox_vrf_dic_all[nbvrf.id] = nbvrf
        if (nbvrf.custom_fields["openstack_networkid"] is not None and
                nbvrf.custom_fields["openstack_networkid"] != "" and
                nbvrf.ipaddress_count == 0 and
                nbvrf.prefix_count == 0 and
                "OpenStack API script" in str(nbvrf.tags)):
            # To delete a VRF, there need to be no IP-addresses or Subnets within it
            # These are the dics we are going to use for a potential delete action
            netbox_vrf_dic_openstack[nbvrf.custom_fields["openstack_networkid"]] = nbvrf
            netbox_vrf_dic_netbox[nbvrf.id] = nbvrf
    for nb_addr_id, nb_addr in netbox_addr_dic.items():
        if nb_addr.vrf is not None and nb_addr.vrf.id in netbox_vrf_dic_all.keys():
            # Only private addresses should have VRFs assigned,
            # We filter for VRFs, assigned to Addresses, assigned to Interfaces, assigned to VMs in our cluster ;)
            nb_vrf = netbox_vrf_dic_all.get(nb_addr.vrf.id)
            netbox_vrf_dic_filtered_netbox[nb_vrf.id] = nb_vrf
        else:
            continue
    print(f"Fetched and built VRF dictionaries")
    return netbox_vrf_dic_openstack, netbox_vrf_dic_netbox, netbox_vrf_dic_filtered_netbox


def get_netbox_prefixes(netbox_vrf_dic):
    # Prefixes
    netboxprefixstotal = nb.ipam.prefixes.all()  # Prefixes don't necessarily have the tag, in case of WAN subnets
    netbox_prefix_dic_filt = {}
    netbox_prefix_dic_openstack = {}
    netbox_prefix_dic_netbox = {}
    for subnet in netboxprefixstotal:
        if subnet.custom_fields["openstack_subnetid"] is not None and subnet.custom_fields["openstack_subnetid"] != "":
            # First we collect all Subnets with an OpenStack ID
            netbox_prefix_dic_filt[subnet.id] = subnet
        else:
            continue
    for prefix_id, prefix in netbox_prefix_dic_filt.items():
        if prefix.vrf is not None and ipaddress.ip_network(prefix.prefix).is_private:
            # We filter for LAN VRFs
            # Only LAN addresses have VRFs assigned to them by our script
            parents = nb.ipam.ip_addresses.filter(parent=prefix.prefix, vrf_id=prefix.vrf.id)
            amountofips = 0
            for ip in parents:
                # We count the number of IPs within the subnet
                amountofips = amountofips + 1
            if amountofips == 0:
                # If the prefix comes back empty, only then do we add the Subnet for potential deletion
                netbox_prefix_dic_openstack[prefix.custom_fields["openstack_subnetid"]] = prefix
                netbox_prefix_dic_netbox[prefix.id] = prefix
            else:
                # If the amount of IPs within the subnet is higher than 0, we do nothing
                continue
        elif (prefix.vrf is None and
              ipaddress.ip_network(prefix.prefix).is_global and
              prefix.custom_fields["openstack_subnetid"] is not None and
              prefix.custom_fields["openstack_subnetid"] != ""):
            # We make sure to filter for Global addresses unassigned to VRFs, but also yoinked by our OpenStack script
            parents = nb.ipam.ip_addresses.filter(parent=prefix.prefix)
            amountofips = 0
            for ip in parents:
                # We count the number of IPs within the subnet
                amountofips = amountofips + 1
            if amountofips == 0:
                # If the prefix comes back empty, only then do we add the Subnet for potential deletion
                netbox_prefix_dic_openstack[prefix.custom_fields["openstack_subnetid"]] = prefix
                netbox_prefix_dic_netbox[prefix.id] = prefix
        else:
            # If the amount of IPs within the subnet is higher than 0, we do nothing
            continue
    print(f"Fetched and built Prefix dictionaries")
    return netbox_prefix_dic_openstack, netbox_prefix_dic_netbox


def get_netbox_volumes():
    # Volumes
    netboxvolumes = nb.virtualization.virtual_disks.filter(tag="openstack-api-script")
    print(f"Fetched Volumes")
    return netboxvolumes


def generateidlists(myinstances, neutron_routers, neutron_server_dictionary):
    # Create sets based on the servers within OpenStack and Netbox, so we can compare them
    myopenstackids = set()
    for server in myinstances:
        # Fill the set with all OpenStack instance IDs
        myopenstackids.add(str(server.id))
    for router in neutron_routers.keys():
        # Add all router IDs to the set as well
        myopenstackids.add(str(router))
    for dhcpserver in neutron_server_dictionary.keys():
        # Add all Neutron server IDs to the set as well
        myopenstackids.add(str(dhcpserver))
    return myopenstackids


def cleannetboxvms(nova_vms, neutron_routers, neutron_agents, nb_vm_os_dic):
    # Delete Netbox VMs based on our collected OpenStack IDs
    myopenstackidlist = generateidlists(nova_vms, neutron_routers, neutron_agents)
    vmstodelete = []
    for nb_vm_os_id in nb_vm_os_dic.keys():
        if nb_vm_os_id not in myopenstackidlist:
            netboxvm = nb_vm_os_dic.get(nb_vm_os_id)
            vmstodelete.append(netboxvm.id)
            print(f"Queueing Netbox VM {netboxvm.name} ID {netboxvm.id} for deletion. OpenStack ID was {nb_vm_os_id}")
        elif nb_vm_os_id in myopenstackidlist:
            continue
    try:
        if not vmstodelete:
            # We evaluate whether there is anything in the array before attempting deletion
            print(f"There were no Netbox VMs to delete!\n")
            pass
        elif vmstodelete:
            print(f"\nDeleting the following Netbox VM IDs in 10 seconds: \n{vmstodelete}\n")
            time.sleep(10)
            nb.virtualization.virtual_machines.delete(vmstodelete)
            print("Succesfully deleted old Netbox VMs!\n")
    except Exception as e:
        print(f"Netbox Instance deletion went wrong \n{e}")
        print(f"Unable to delete \n{vmstodelete}")
        sys.exit(1)


def cleanvolumes(nb_vm_dic_nb, nb_volumes, cindervolumes):
    try:
        # Collect all IDs of VMs in the Netbox cluster
        netboxvdisks = set()
        netboxvddeleteid = []
        for nbvol in nb_volumes:
            if nbvol.virtual_machine.id in nb_vm_dic_nb.keys():
                # Check whether NB Virtual Disks are bound to NB VMs in the cluster, and add them to the set if so
                netboxvdisks.add(nbvol)
            else:
                continue
        for nbdisk in netboxvdisks:
            if nbdisk.custom_fields["openstack_volumeid"] not in cindervolumes.keys():
                # If the OpenStack ID is found in NetBox, but not by Cinder, we queue the Volume for deletion
                netboxvddeleteid.append(str(nbdisk.id))
                print(f"Queueing Netbox Virtual Disk {nbdisk.name} VM {nbdisk.virtual_machine.name} as it is not attached to anything")
        try:
            if not netboxvddeleteid:
                # We evaluate whether there is anything in the array before attempting deletion
                print(f"There were no NetBox Virtual Disks to delete!\n")
                pass
            elif netboxvddeleteid:
                # Finally we attempt deleting the old Virtual Disks
                print(f"\nDeleting the following NetBox Virtual Disks IDs in 10 seconds: \n{netboxvddeleteid}\n")
                time.sleep(10)
                nb.virtualization.virtual_disks.delete(netboxvddeleteid)
                print(f"Succesfully deleted old NetBox Virtual Disks.\n")
        except Exception as e:
            print(f"Unable to delete \n{netboxvddeleteid}  \n{e}")
            sys.exit(1)
    except Exception as e:
        print(f"Netbox and Cinder disk comparison went wrong \n{e}")
        sys.exit(1)


def cleaninterfaces(neutroninterfaces, netbox_interface_os_dic):
    try:
        netboxinterfacetodelete = []
        for nb_int_os_id, nb_int in netbox_interface_os_dic.items():
            if nb_int_os_id not in neutroninterfaces.keys():
                # If non-relevant Openstack-Interface IDs are found in Netbox, we append the interface for deletion
                netboxinterfacetodelete.append(nb_int.id)
                print(f"Queueing Interface {nb_int.name} ID {nb_int.id} of VM {nb_int.virtual_machine.name} "
                      f"as it is not attached to anything of relevance")
            else:
                continue
    except Exception as e:
        print(f"Netbox and Neutron interface comparison went wrong \n{e}")
        sys.exit(1)
    try:
        if not netboxinterfacetodelete:
            # We evaluate whether there is anything in the array before attempting deletion
            print(f"There were no NetBox Interfaces to delete!\n")
            pass
        elif netboxinterfacetodelete:
            print(f"\nDeleting the following NetBox Interface IDs in 10 seconds: \n{netboxinterfacetodelete}\n")
            time.sleep(10)
            nb.virtualization.interfaces.delete(netboxinterfacetodelete)
            print(f"Succesfully deleted old NetBox Interfaces.\n")
    except Exception as e:
        print(f"Unable to delete \n{netboxinterfacetodelete}  \n{e}")
        sys.exit(1)


def cleanaddresses(neutroninterfaces, neutronfloat, nb_addresses, netbox_int_dic):
    # We match NetBox addresses to Neutron Nova/Float addresses
    netboxaddressesdeleteid = []
    for nb_address_id, nb_address in nb_addresses.items():
        address_interface = netbox_int_dic.get(nb_address.assigned_object.id)
        nb_interface_os_id = address_interface.custom_fields['openstack_interfaceid']
        neutron_addresses = set()
        split_address = str(nb_address.address)
        split_address = split_address.split('/')[0]  # NB always gives along the prefix, but Neutron doesn't
        for ip in neutroninterfaces[nb_interface_os_id]["interfaceips"]:
            neutron_addresses.add(ip["ip_address"])
        for floatid in neutronfloat:
            if neutronfloat[floatid]["boundtointerfaceid"] == nb_interface_os_id:
                # I'm sorry for looping over the entire dictionary each time ;_;
                # We fetch any relevant Floating IPs from our other dictionary and add them our address collection
                neutron_addresses.add(neutronfloat[floatid]["floatip"])
        if split_address in neutron_addresses:
            continue
        elif split_address not in neutron_addresses:
            # Finally, we check if the NB address is not in our Neutron address set.
            print(f"Queueing Address {nb_address.address} as it does not exist on OpenStack Interface {nb_interface_os_id}")
            netboxaddressesdeleteid.append(nb_address.id)
    try:
        if not netboxaddressesdeleteid:
            # We evaluate whether there is anything in the array before attempting deletion
            print(f"There were no NetBox addresses to delete!\n")
            pass
        elif netboxaddressesdeleteid:
            # We attempt to delete the empty OpenStack VRFs
            print(f"\nDeleting the following NetBox address IDs in 10 seconds: \n{netboxaddressesdeleteid}\n")
            time.sleep(10)
            nb.ipam.ip_addresses.delete(netboxaddressesdeleteid)
            print(f"Succesfully deleted irrelevant NetBox addresses.\n")
    except Exception as e:
        print(f"Unable to delete \n{netboxaddressesdeleteid} \n{e}")
        sys.exit(1)


def cleansubnets(nb_prefix_dic_nb):
    # We delete empty Prefixes here
    netboxprefixesdeleteid = []
    for nb_prefix_id, nb_prefix in nb_prefix_dic_nb.items():
        if ipaddress.ip_network(nb_prefix).is_global:
            # Our filtered WAN subnets, used by our/an OpenStack cluster,
            # We already checked whether these WAN subnets were empty, but I think it's somewhat rude to delete them
            # So I've elected to ignore these Prefixes
            continue
        elif ipaddress.ip_network(nb_prefix.prefix).is_private:
            # if nb_prefix.custom_fields["openstack_subnetid"] not in os_subnet_dic.keys():
            # We don't match to anything in Neutron, but rather only care whether the NetBox Prefixes are in use or not
            print(f"Queueing LAN Prefix {nb_prefix.prefix} ID {nb_prefix_id} because it contains no IP-addresses. "
                  f"OpenStack ID is or was {nb_prefix.custom_fields['openstack_subnetid']}")
            netboxprefixesdeleteid.append(nb_prefix_id)
    try:
        if not netboxprefixesdeleteid:
            # We evaluate whether there is anything in the array before attempting deletion
            print(f"There were no NetBox Prefixes to delete!\n")
            pass
        elif netboxprefixesdeleteid:
            # We attempt to delete the empty OpenStack Subnets
            print(f"\nDeleting the following NetBox Prefixes IDs in 10 seconds: \n{netboxprefixesdeleteid}\n")
            time.sleep(10)
            nb.ipam.prefixes.delete(netboxprefixesdeleteid)
            print(f"Succesfully deleted irrelevant NetBox Prefixes.\n")
    except Exception as e:
        print(f"Unable to delete \n{netboxprefixesdeleteid} \n{e}")
        sys.exit(1)


def cleanvrfs(nb_vrf_dic_nb):
    netboxvrfsdeleteid = []
    for vrf_id, vrf in nb_vrf_dic_nb.items():
        if vrf.ipaddress_count == 0 and vrf.prefix_count == 0:
            # Kinda useless double-check before we append for deletion
            # At this point, any old NetBox VMs should have been deleted, including their Interfaces and IP-addresses
            # For a VRF to be deleted, all IP-addresses within said VRF should be deleted first, and the Subnet as well
            # Either we've already removed everything properly,
            # or there is something in the VRF that /shouldn't/ be in there
            netboxvrfsdeleteid.append(str(vrf.id))
            print(f"Queueing NetBox VRF {vrf.name} for deletion because it contains no IP-adresses.")
        else:
            continue
    try:
        if not netboxvrfsdeleteid:
            # We evaluate whether there is anything in the array before attempting deletion
            print(f"There were no NetBox VRFs to delete!\n")
            pass
        elif netboxvrfsdeleteid:
            # We attempt to delete the empty OpenStack VRFs
            print(f"\nDeleting the following NetBox VRF IDs in 10 seconds: \n{netboxvrfsdeleteid}\n")
            time.sleep(10)
            nb.ipam.vrfs.delete(netboxvrfsdeleteid)
            print(f"Succesfully deleted empty NetBox VRFs.\n")
    except Exception as e:
        print(f"Unable to delete \n{netboxvrfsdeleteid} \n{e}")
        sys.exit(1)


try:
    print(f'\nFetching information from OpenStack \n')
    nova_instances, nova_flavor_dictionary = get_nova()
    cinder_volume_dictionary = get_cinder()
    (neutron_interface_dictionary, neutron_network_private_dictionary, neutron_float_dictionary, neutron_router_dictionary,
     neutron_dhcpagent_dictionary, neutron_subnet_dictionary) = get_neutron()
    print(f'Finished fetching information from OpenStack. \n')
except Exception as e:
    print(f"Unable to collect information from OpenStack \n{e}")
    sys.exit(1)


try:
    netbox_vm_dic_os, netbox_vm_dic_nb = get_netbox_vms()
except Exception as e:
    print(f"Unable to collect VM information from NetBox \n{e}")
    sys.exit(1)


try:
    # Delete Netbox VMs that are not in OpenStack
    print(f"\nAttempting to delete old NetBox Virtual Machines.")
    cleannetboxvms(nova_instances, neutron_router_dictionary, neutron_dhcpagent_dictionary, netbox_vm_dic_os)
except Exception as e:
    print(f"Error deleting old NetBox Virtual Machines \n{e}")
    sys.exit(1)


try:
    print(f'Fetching VM, Volume and Interface information from NetBox for cluster {cluster_name}')
    netbox_vm_dic_os, netbox_vm_dic_nb = get_netbox_vms()
    netbox_volumes = get_netbox_volumes()
    netbox_int_dic_os, netbox_int_dic_nb = get_netbox_interfaces(netbox_vm_dic_nb)
except Exception as e:
    print(f"Unable to collect information from NetBox \n{e}")
    sys.exit(1)


try:
    # Delete NetBox Virtual Disks that are not bound to OpenStack Instances
    print(f"\nAttempting to delete old NetBox Virtual Disks.")
    cleanvolumes(netbox_vm_dic_nb, netbox_volumes, cinder_volume_dictionary)
except Exception as e:
    print(f"Error deleting old NetBox Virtual Disks \n{e}")
    sys.exit(1)


try:
    # Delete Netbox interfaces that are not bound to OpenStack Instances
    print(f"Attempting to delete old NetBox Interfaces.")
    cleaninterfaces(neutron_interface_dictionary, netbox_int_dic_os)
except Exception as e:
    print(f"Error deleting old NetBox interfaces\n{e}")
    sys.exit(1)


try:
    print(f'Fetching Interface, Address, VRF and Prefix information from NetBox for cluster {cluster_name}')
    netbox_int_dic_os, netbox_int_dic_nb = get_netbox_interfaces(netbox_vm_dic_nb)
    netbox_addr_dic_nb = get_netbox_addresses(netbox_int_dic_nb)
    netbox_vrf_dic_os, netbox_vrf_dic_nb, netbox_vrf_dic_filtered_nb = get_netbox_vrfs(netbox_addr_dic_nb)
except Exception as e:
    print(f"Unable to collect information from NetBox \n{e}")
    sys.exit(1)


try:
    # Delete Netbox Interface addresses that are not found on their respective OpenStack Interface
    print(f"\nAttempting to delete old IP-addresses not found on OpenStack Interfaces.")
    cleanaddresses(neutron_interface_dictionary, neutron_float_dictionary, netbox_addr_dic_nb, netbox_int_dic_nb)
except Exception as e:
    print(f"Error deleting old NetBox IP-addresses \n{e}")
    sys.exit(1)


try:
    print(f"Fetching Address, Prefix and VRF information from NetBox as states may have changed")
    netbox_addr_dic_nb = get_netbox_addresses(netbox_int_dic_nb)
    netbox_vrf_dic_os, netbox_vrf_dic_nb, netbox_vrf_dic_filtered_nb = get_netbox_vrfs(netbox_addr_dic_nb)
    netbox_prefix_dic_os, netbox_prefix_dic_nb = get_netbox_prefixes(netbox_vrf_dic_filtered_nb)
except Exception as e:
    print(f"Error re-fetching Prefix and VRF information \n{e}")
    sys.exit(1)


try:
    # Delete Netbox OpenStack Prefixes that are devoid of IP-addresses
    print(f"\nAttempting to delete empty Netbox Prefixes that were created by OpenStack2NetBox.")
    cleansubnets(netbox_prefix_dic_nb)
except Exception as e:
    print(f"Error deleting empty NetBox prefixes \n{e}")
    sys.exit(1)


try:
    print(f"Re-fetching VRF information one final time")
    netbox_vrf_dic_os, netbox_vrf_dic_nb, netbox_vrf_dic_filtered_nb = get_netbox_vrfs(netbox_addr_dic_nb)
except Exception as e:
    print(f"Error re-fetching VRF information \n{e}")
    sys.exit(1)


try:
    # Delete Netbox VRFs that contain no IP-adresses or Prefixes
    print(f"\nAttempting to delete empty NetBox VRFs, containing the tag 'openstack-api-script'.")
    cleanvrfs(netbox_vrf_dic_nb)
except Exception as e:
    print(f"Error deleting empty NetBox VRFs\n{e}")
    sys.exit(1)


'''
print(netbox_vm_dic_os, netbox_vm_dic_nb)
print(netbox_int_dic_os, netbox_int_dic_nb)
print(netbox_addr_dic_nb)
print(netbox_vrf_dic_os, netbox_vrf_dic_nb, netbox_vrf_dic_filtered_nb)
print(netbox_prefix_dic_os, netbox_prefix_dic_nb)
print(netbox_volumes)
'''

print(f"\nThe deletion script has finished succesfully!")
