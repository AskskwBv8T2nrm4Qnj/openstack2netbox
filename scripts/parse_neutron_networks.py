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

from scripts.netbox.update import updatenetboxvrf
from scripts.netbox.update import updatenetboxsubnet
from scripts.netbox.update import updatenetboxglobalsubnet

from scripts.netbox.create import createnetboxvrf
from scripts.netbox.create import createnetboxglobalsubnet
from scripts.netbox.create import createnetboxprivatesubnet

import settings
cluster_name = settings.cluster_name

unchangedvrfs = 0
unchangedsubnets = 0


def netboxipamvrfs(openstack_vrf_dic, netbox_vrf_dic):
    # We create the actual Netbox VRFs, checking inside Netbox if they are new OpenStack networks or already existing
    global unchangedvrfs
    for openstacknetworkid, openstacknetworkname in openstack_vrf_dic.items():
        customvrfname = f"OpenStack_{cluster_name}_{openstacknetworkname}"  # Define a VRF-name based on the network the address is in
        customvrfname = str(customvrfname[:64])  # NetBox API doesn't take more than 64 characters
        if openstacknetworkid in netbox_vrf_dic.keys():
            # We check whether the VRF exists and return its ID if it does
            nb_vrf = netbox_vrf_dic.get(openstacknetworkid)
            nb_vrf_shortname = f"OpenStack_{cluster_name}_"
            try:
                if ((nb_vrf.name != customvrfname and nb_vrf_shortname not in nb_vrf.name) or
                        customvrfname == nb_vrf.name):
                    # We give people the opportunity to keep custom NetBox VRF-names,
                    # But only if said VRF has the correct Openstack Network ID and our tag applied
                    # Furthermore the only thing that can be changed is the name, so we do nothing if it still the same
                    unchangedvrfs = unchangedvrfs + 1
                    if (unchangedvrfs % 10) == 0:
                        print(f"Skipped {unchangedvrfs} NetBox VRFS because nothing changed")
                    else:
                        pass
                    continue
                else:
                    # We only have the name that we could possibly update...
                    updatenetboxvrf(customvrfname, nb_vrf.id)
                    print(f'Updated Netbox VRF {customvrfname} because ID {openstacknetworkid} was found')
            except Exception as e:
                print(f"Unable to update Netbox VRF {customvrfname} \n{e}")
                sys.exit(1)
        elif openstacknetworkid not in netbox_vrf_dic.keys():
            # If the VRF does not exist yet, we create it
            try:
                createnetboxvrf(customvrfname, openstacknetworkid)
                print(f'Created Netbox VRF {customvrfname} because it contains one or more RFC1918 IPs')
            except Exception as e:
                print(f"Unable to create Netbox VRF {customvrfname} \n{e}")
                sys.exit(1)
    print(f"Skipped {unchangedvrfs} VRFS in total, because there were no changes.")


def netboxipamsubnets(openstack_subnet_dic, openstack_interface_dic, netbox_subnet_dic, netbox_vrf_dic):
    # We check our subnet data and forward the information to the parsing function
    global unchangedsubnets
    unique_subnets = {}
    for interface in openstack_interface_dic:
        # Our Interface dictionary was already filtered down to IPs and subnets we will be adding to NetBox
        # So we just grab the subnet-ID for each IP,
        # and use that to look in our Subnet dictionary for our values CIDR/Prefix
        for ip in openstack_interface_dic[interface]['interfaceips']:
            subnet_id = ip['subnet_id']
            if subnet_id in openstack_subnet_dic.keys():
                # We fill a new dictionary because we only want to pass a unique
                # Subnet combination to NetBox, rather than throwing a Subnet at NetBox for each IP/Interface
                unique_subnets[subnet_id] = {'subnet_id': subnet_id,
                                              'subnet_name': openstack_subnet_dic[subnet_id]['subnet_name'],
                                              'subnet_network_id': openstack_subnet_dic[subnet_id]['subnet_network_id'],
                                              'subnet_cidr': openstack_subnet_dic[subnet_id]['subnet_cidr'],
                                              'subnet_prefix': openstack_subnet_dic[subnet_id]['subnet_prefix']
                                             }
    for subnet in unique_subnets:
        try:
            openstack_subnet_obj = CreateNetboxSubnetObject(unique_subnets[subnet])
            parsesubnet(openstack_subnet_obj, netbox_subnet_dic, netbox_vrf_dic)
        except Exception as e:
            print(f"Unable to define OpenStack subnet object {subnet} \n{e}")
            sys.exit(1)
    print(f"Skipped {unchangedsubnets} prefixes in total, because there were no changes.")


class CreateNetboxSubnetObject(object):
    def __init__(self, dictionary):
        self.name = dictionary['subnet_name']
        self.subnet_id = dictionary['subnet_id']
        self.network_id = dictionary['subnet_network_id']
        self.cidr = dictionary['subnet_cidr']
        self.prefix = dictionary['subnet_prefix']


def parsesubnet(os_subnet, netbox_subnet_dic, netbox_vrf_dic):
    try:
        os_subnet_cidr = os_subnet.cidr
        os_subnet_id = os_subnet.subnet_id
        os_subnet_network_id = os_subnet.network_id
        if os_subnet_id in netbox_subnet_dic.keys():
            # First we check whether this subnet OS ID exists in NetBox and then update it
            # regardless of private/public state
            netbox_prefix = netbox_subnet_dic.get(os_subnet_id)
            comparsubnets(os_subnet, netbox_prefix)
        elif (os_subnet_id not in netbox_subnet_dic.keys() and
              os_subnet_cidr not in netbox_subnet_dic.keys() and
              ipaddress.ip_network(os_subnet_cidr).is_global):
            # If the Global subnet doesn't exist in NetBox, we create it in the Global VRF
            createnetboxglobalsubnet(os_subnet)
        elif (os_subnet_id not in netbox_subnet_dic.keys() and
              os_subnet_cidr in netbox_subnet_dic.keys() and
              ipaddress.ip_network(os_subnet_cidr).is_global):
            # If the Global subnet does exist in NetBox but without an OpenStack ID, we update it with the ID
            # We don't compare whether the Subnet ID in OpenStack is the same as in NetBox,
            # because we don't want to cause ownership-fights if multiple OpenStack environments use the same subnet
            netbox_prefix = netbox_subnet_dic.get(os_subnet_cidr)
            if netbox_prefix.custom_fields["openstack_subnetid"] == "":
                updatenetboxglobalsubnet(os_subnet, netbox_prefix)
            else:
                print(f"Skipped updating Global Prefix {netbox_prefix}. It's OpenStack ID is defined but doesn't match")
                pass
        elif os_subnet_id not in netbox_subnet_dic.keys() and ipaddress.ip_network(os_subnet_cidr).is_private:
            # If the private subnet doesn't exist in NetBox, we create it in a specific VRF
            netbox_vrf = netbox_vrf_dic.get(os_subnet_network_id)
            createnetboxprivatesubnet(os_subnet, netbox_vrf)
        else:
            print(f"Subnet {os_subnet} is in a weird situation and now the script is unhappy. Good job.")
            sys.exit(1)
    except Exception as e:
        print(f"Unable to create or update OpenStack Subnet {os_subnet} \n{e}")
        print(vars(os_subnet))
        sys.exit(1)


def comparsubnets(os_subnet, netbox_prefix):
    global unchangedsubnets
    try:
        if os_subnet.cidr != netbox_prefix.prefix:
            # We can really only update a single useful parameter, I mean, what are you going to do... migrate it?? Haha
            updatenetboxsubnet(os_subnet, netbox_prefix)
        else:
            unchangedsubnets = unchangedsubnets + 1
            if (unchangedsubnets % 10) == 0:
                print(f"Skipped {unchangedsubnets} NetBox prefixes because nothing changed")
            else:
                pass
            pass
    except Exception as e:
        print(f"Unable to compare states for Subnet {os_subnet} \n{e}")
        print(vars(os_subnet))
        sys.exit(1)
