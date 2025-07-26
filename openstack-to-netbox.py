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
import time

from scripts.openstack.fetchinfo import get_keystone
from scripts.openstack.fetchinfo import get_nova
from scripts.openstack.fetchinfo import get_cinder
from scripts.openstack.fetchinfo import get_neutron

from scripts.netbox.fetchinfo import nbfetchinterfaces
from scripts.netbox.fetchinfo import nbfetchvms
from scripts.netbox.fetchinfo import nbfetchvolumes
from scripts.netbox.fetchinfo import nbfetchvrfs
from scripts.netbox.fetchinfo import nbfetchsubnets
from scripts.netbox.fetchinfo import nbfetchaddresses

from scripts.parse_nova_vm import nova_to_netboxvms
from scripts.parse_neutron_vm import neutronrouter_to_netboxvms
from scripts.parse_neutron_vm import neutrondhcp_to_netboxvms
from scripts.parse_cinder_volumes import cinder_to_netboxdisks
from scripts.parse_neutron_interfaces import netboxinterfaces
from scripts.parse_neutron_interfaces import netboxmacs
from scripts.parse_neutron_networks import netboxipamvrfs
from scripts.parse_neutron_networks import netboxipamsubnets
from scripts.parse_neutron_ipam import netboxipam
from scripts.parse_neutron_ipam import netboxipamfloat

import settings
nb = settings.nb
cluster_name = settings.cluster_name
cluster_type = settings.cluster_type

try:
    print(f'\nFetching information from OpenStack \n')
    keystone_tenant_dictionary = get_keystone()
    nova_instances, nova_flavor_dictionary = get_nova()
    cinder_volume_dictionary = get_cinder()
    (neutron_interface_dictionary, neutron_network_private_dictionary, neutron_float_dictionary,
     neutron_router_dictionary, neutron_dhcpagent_dictionary, neutron_subnet_dictionary) = get_neutron()
    print(f'Finished fetching information from OpenStack. \n')
except Exception as e:
    print(f"Unable to collect information from OpenStack \n{e}")
    sys.exit(1)

try:
    print(f'Fetching information from NetBox for cluster {cluster_name}\n')
    netboxvmdic = nbfetchvms()
    netboxinterfacedic = nbfetchinterfaces()
    netboxvoldic = nbfetchvolumes()
    netboxvrfdic = nbfetchvrfs()
    netboxsubnetdic = nbfetchsubnets()
    netboxlanaddressdic, netboxwanaddressdic = nbfetchaddresses()
    print(f'\nFinished collecting information from NetBox for cluster {cluster_name}')
except Exception as e:
    print(f"Unable to collect information from NetBox \n{e}")
    sys.exit(1)


print(f'Creation and or updating of NetBox objects will start in 5 seconds. \n')
time.sleep(5)


try:
    print(f"Attempting to create/update NetBox Virtual Machines based on OpenStack Instances")
    nova_to_netboxvms(nova_instances, nova_flavor_dictionary, keystone_tenant_dictionary, netboxvmdic)
    print('NetBox Virtual Machines have been created or updated succesfully \n')
except Exception as e:
    # We really only want to proceed to the next functions, when the previous step has been completed succesfully
    print(f"NetBox Virtual Machine creation or updating failed \n{e}")
    sys.exit(1)


try:
    print(f"Attempting to create/update NetBox Virtual Machines based on OpenStack routers")
    neutronrouter_to_netboxvms(neutron_router_dictionary, nova_flavor_dictionary,
                               keystone_tenant_dictionary, netboxvmdic)
    print('NetBox routers have been created or updated succesfully \n')
except Exception as e:
    print(f"NetBox Router creation or updating failed \n{e}")
    sys.exit(1)


try:
    print(f"Attempting to create/update NetBox Virtual Machines based on Neutron DHCP agents")
    neutrondhcp_to_netboxvms(neutron_dhcpagent_dictionary, netboxvmdic)
    print('NetBox DHCP agents have been created or updated succesfully \n')
except Exception as e:
    print(f"NetBox DHCP agent creation or updating failed \n{e}")
    sys.exit(1)


try:
    print(f"Re-fetching Virtual Machines from NetBox as states may have been modified")
    netboxvmdic = nbfetchvms()
except Exception as e:
    print(f"Unable to re-fetch Virtual Machines from NetBox cluster {cluster_name} \n{e}")
    sys.exit(1)


try:
    print(f"\nAttempting to create/update Netbox Virtual Disks based on Volumes associated with OpenStack Instances")
    cinder_to_netboxdisks(cinder_volume_dictionary, netboxvoldic, netboxvmdic)
    print(f'NetBox disks have been created or updated succesfully \n')
except Exception as e:
    print(f"NetBox disk creation or updating failed \n{e}")
    sys.exit(1)


try:
    print(f"Attempting to create/update Netbox Interfaces based on interfaces associated with OpenStack Instances")
    netboxinterfaces(neutron_interface_dictionary, netboxinterfacedic, netboxvmdic)
    print('NetBox Interfaces have been created or updated succesfully \n')
except Exception as e:
    print(f"NetBox Interfaces creation or updating failed \n{e}")
    sys.exit(1)


try:
    print(f'Re-fetching NetBox Interfaces information')
    netboxinterfacedic = nbfetchinterfaces()
    print(f'Finished re-fetching NetBox Interfaces \n')
except Exception as e:
    print(f"Unable to collect Interface information from NetBox \n{e}")
    sys.exit(1)


try:
    print(f"Attempting to create and or associate NetBox MAC-addresses based on Neutron interfaces.")
    netboxmacs(neutron_interface_dictionary, netboxinterfacedic)
    print('NetBox MAC-addresses have been created and or associated succesfully \n')
except Exception as e:
    print(f"NetBox MAC-addresses creation or associating failed \n{e}")
    sys.exit(1)


try:
    print(f"Attempting to create/update Netbox VRFs based on OpenStack networks containing private IP-addresses")
    netboxipamvrfs(neutron_network_private_dictionary, netboxvrfdic)
    print(f"NetBox VRFs have been created or updated succesfully \n")
    try:
        print(f'Re-fetching NetBox VRF information')
        netboxvrfdic = nbfetchvrfs()
    except Exception as e:
        print(f"Unable to collect VRF information from NetBox \n{e}")
        sys.exit(1)
    try:
        print(f"\nAttempting to create/update NetBox subnets based on OpenStack subnets containing relevant addresses")
        netboxipamsubnets(neutron_subnet_dictionary, neutron_interface_dictionary, netboxsubnetdic, netboxvrfdic)
        print(f"NetBox subnets have been created or updated succesfully \n")
    except Exception as e:
        print(f"NetBox subnets based on OpenStack subnets creation or updating failed \n{e}")
        sys.exit(1)
except Exception as e:
    print(f"NetBox VRF creation or updating failed \n{e}")
    sys.exit(1)


try:
    print(f'Re-fetching NetBox subnet information')
    netboxsubnetdic = nbfetchsubnets()
except Exception as e:
    print(f"Unable to collect subnet information from NetBox \n{e}")
    sys.exit(1)


try:
    print(f"\nAttempting to create/update NetBox IP-addresses based on Interfaces bound to OpenStack Instances")
    netboxipam(neutron_interface_dictionary, neutron_subnet_dictionary, netboxvmdic, netboxinterfacedic, netboxvrfdic,
               netboxlanaddressdic, netboxwanaddressdic)
    print(f'NetBox IP-addresses based on OpenStack Interfaces have been created or updated succesfully \n')
except Exception as e:
    print(f"NetBox IP-addresses based on Instance Interfaces creation or updating failed \n{e}")
    sys.exit(1)


try:
    print(f"Attempting to create/update NetBox IP-addresses based on Floating-IPs bound to Instances")
    netboxipamfloat(neutron_float_dictionary, neutron_subnet_dictionary, netboxvmdic, netboxinterfacedic, netboxvrfdic,
                    netboxlanaddressdic, netboxwanaddressdic)
    print(f'NetBox IP-addresses based on Floating-IPs have been created or updated succesfully \n')
    print(f"The script has finished succesfully!")
except Exception as e:
    print(f"NetBox IP-addresses based on Floating-IPs creation or updating failed \n{e}")
    sys.exit(1)
