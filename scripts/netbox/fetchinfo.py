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
import ipaddress

import settings
nb = settings.nb
cluster_name = settings.cluster_name


def nbfetchvms():
    try:
        netbox_vm_dictionary = {}
        for nbvm in nb.virtualization.virtual_machines.filter(tag="openstack-api-script", cluster=cluster_name):
            netbox_vm_dictionary[nbvm.custom_fields["openstack_id"]] = nbvm
    except Exception as e:
        print(f"Unable to collect Netbox Virtual Machines \n{e}")
        sys.exit(1)
    print("Fetched NetBox Virtual Machines")
    return netbox_vm_dictionary


def nbfetchvolumes():
    try:
        # Collect all IDs of VMs in the Netbox cluster
        netboxvolumes = nb.virtualization.virtual_disks.filter(tag="openstack-api-script")
        netboxclustervms = nb.virtualization.virtual_machines.filter(tag="openstack-api-script", cluster=cluster_name)
        netboxclustervmids = set()
        netbox_vol_dictionary = {}
        for vm in netboxclustervms:
            # NB Virtual Disks lack information, so first collect the Clusters' VM IDs instead
            netboxclustervmids.add(str(vm.id))
        for nbvol in netboxvolumes:
            if str(nbvol.virtual_machine.id) in netboxclustervmids:
                # Check whether NB Virtual Disks are bound to NB VMs in the cluster, and add them to the set if so
                netbox_vol_dictionary[nbvol.custom_fields["openstack_volumeid"]] = nbvol
    except Exception as e:
        print(f"Netbox and Cinder disk comparison went wrong \n{e}")
        sys.exit(1)
    print("Fetched NetBox Virtual Disks")
    return netbox_vol_dictionary


def nbfetchinterfaces():
    try:
        netboxclustervmids = set()
        netboxinterfacestotal = nb.virtualization.interfaces.filter(tag="openstack-api-script")
        netbox_int_dictionary = {}
        for vm in nb.virtualization.virtual_machines.filter(tag="openstack-api-script", cluster=cluster_name):
            # NB Interfaces lack information, so first collect the Clusters' VM IDs instead
            netboxclustervmids.add(str(vm.id))
        for nbinterface in netboxinterfacestotal:
            if str(nbinterface.virtual_machine.id) in netboxclustervmids:
                # Collect Netbox OpenStack Interface IDs, only if said interface is bound to a VM that is in our cluster
                netbox_int_dictionary[nbinterface.custom_fields["openstack_interfaceid"]] = nbinterface
    except Exception as e:
        print(f"Unable to collect Netbox Interfaces \n{e}")
        sys.exit(1)
    print("Fetched NetBox Interfaces")
    return netbox_int_dictionary


def nbfetchvrfs():
    try:
        netboxvrfstotal = nb.ipam.vrfs.all()
        # We fetch all VRFs and check all of them for potential OpenStack Neutron IDs
        netbox_vrf_dictionary = {}
        for nbvrf in netboxvrfstotal:
            if (nbvrf.custom_fields["openstack_networkid"] is not None and
                    nbvrf.custom_fields["openstack_networkid"] != ""):
                nb_os_id = str(nbvrf.custom_fields["openstack_networkid"])
                if " " in nb_os_id:
                    print(f"There's a space in {nbvrf.name} ID {nbvrf.id}. Please remove it!")
                    sys.exit(1)
                elif "," in nb_os_id:
                    # We give people the opportunity to combine different OpenStack Neutron networks in NetBox
                    nb_os_id = nb_os_id.split(',')
                    for os_id in nb_os_id:
                        netbox_vrf_dictionary[os_id] = nbvrf
                else:
                    netbox_vrf_dictionary[nb_os_id] = nbvrf
            else:
                continue
    except Exception as e:
        print(f"Unable to collect Netbox VRFs \n{e}")
        sys.exit(1)
    print("Fetched NetBox VRFs")
    return netbox_vrf_dictionary


def nbfetchsubnets():
    try:
        netboxprefixstotal = nb.ipam.prefixes.filter()  # Prefixes don't necessarily have the tag, in case of WAN subnets
        netbox_prefix_dictionary = {}
        for subnet in netboxprefixstotal:
            if ipaddress.ip_network(subnet.prefix).is_global:
                # We want the ability to filter for Global prefixes already existing in NetBox
                netbox_prefix_dictionary[subnet.prefix] = subnet
            else:
                pass
            if subnet.custom_fields["openstack_subnetid"] is not None:
                # But we also want the ability to filter for OpenStack subnet IDs
                netbox_prefix_dictionary[subnet.custom_fields["openstack_subnetid"]] = subnet
            else:
                pass
    except Exception as e:
        print(f"Unable to collect Netbox Prefixes \n{e}")
        sys.exit(1)
    print("Fetched NetBox Prefixes")
    return netbox_prefix_dictionary


def nbfetchaddresses():
    # All private addresses we create for OpenStack have the "openstack-api-script"
    # But WAN addresses don't necessarily have the tag because we want to play nice
    # So we create 2 dictionaries, one with all filtered LAN IPs and another with just all the global ones
    try:
        netboxaddresses = nb.ipam.ip_addresses.filter()
        netbox_lan_addresses_dic = {}
        netbox_wan_addresses_dic = {}
        for ip in netboxaddresses:
            prefixed_ip = str(ip.address)
            unprefixed_ip = prefixed_ip.split('/', 1)[0]
            # We use unprefixed_ip because NB always includes the subnet when returning address data
            if "OpenStack API script" in str(ip.tags) and ipaddress.ip_address(unprefixed_ip).is_private:
                # We over-fetch here, in case you have multiple OpenStack clusters
                netbox_lan_addresses_dic[unprefixed_ip] = ip
            elif ipaddress.ip_address(unprefixed_ip).is_global:
                netbox_wan_addresses_dic[unprefixed_ip] = ip
            else:
                pass
    except Exception as e:
        print(f"Unable to collect Netbox addresses \n{e}")
        sys.exit(1)
    print("Fetched NetBox addresses")
    return netbox_lan_addresses_dic, netbox_wan_addresses_dic
