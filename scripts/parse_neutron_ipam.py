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

from scripts.netbox.create import createglobalipamip
from scripts.netbox.create import createlanipamip

from scripts.netbox.update import updateglobalipamip
from scripts.netbox.update import updatelanipamip

import settings
nb = settings.nb
cluster_name = settings.cluster_name

unchanged_wan_ips = 0
unchanged_lan_ips = 0


def netboxipam(neutronintdic, neutronsubnetdictionary, netbox_vm_dictionary, netbox_interface_dictionary,
               netbox_vrf_dictionary, netbox_lan_address_dictionary, netbox_wan_address_dictionary):
    # We parse the values in neutronintdic, and run the Netbox IP-creation functions based on the populated values
    global unchanged_wan_ips
    global unchanged_lan_ips
    skippedips = 0
    for portid in neutronintdic:
        if neutronintdic[portid]['interfaceid'] not in netbox_interface_dictionary.keys():
            # In case there are Interfaces that are attached to Instances, which are not within this Tenant
            skippedips = skippedips + 1
            if (skippedips % 10) == 0:
                print(f"Skipped {skippedips} OpenStack addresses attached to Interfaces that don't exist in NetBox.")
            continue
        else:
            pass
        try:
            openstackinstanceid = neutronintdic[portid]['interfaceassociation']
            openstackinterfaceid = neutronintdic[portid]['interfaceid']
            openstacktackipstatus = neutronintdic[portid]['interfacestatus']
            netboxvm = netbox_vm_dictionary.get(openstackinstanceid)
            netboxinterface = netbox_interface_dictionary.get(openstackinterfaceid)
            if neutronintdic[portid]['osifdeviceowner'] == "network:dhcp":
                openstacktackipstatus = "dhcp"
            elif openstacktackipstatus == "DOWN":
                # Unbound Interfaces in OpenStack are considered DOWN, but they may be bound at any point
                # Furthermore, a compute:nova Interface may be down
                openstacktackipstatus = "reserved"
            else:
                openstacktackipstatus = "active"
            for ip in neutronintdic[portid]['interfaceips']:
                # We rotate through the dictionary in case multiple IPs were associated with a single interface
                openstackip = ip['ip_address']
                # We manually splash together the address + prefix, using our subnet dictionary to find the prefix
                # OpenStack Neutron Interface call does not give the prefix,
                # so if you were to add it to NB now, it will be auto-added as a /32
                openstack_subnet = neutronsubnetdictionary.get(ip['subnet_id'])
                full_openstack_ip = str(openstackip) + "/" + str(openstack_subnet["subnet_prefix"])
                if ipaddress.ip_address(openstackip).is_global:
                    address_summary = CreateAddressObject(full_openstack_ip, openstacktackipstatus, netboxinterface.id,
                                                          netboxinterface.name, netboxvm.id, netboxvm.name)
                    netboxipamglobalip(openstackip, address_summary, netbox_wan_address_dictionary)
                elif ipaddress.ip_address(openstackip).is_private:
                    # If the IP is private, we fetch the VRF we created in the VRF-parser function to add the IP to it
                    openstacknetworkid = neutronintdic[portid]['interfacenetwork']
                    netboxvrf = netbox_vrf_dictionary.get(openstacknetworkid)
                    address_summary = CreateAddressObject(full_openstack_ip, openstacktackipstatus, netboxinterface.id,
                                                          netboxinterface.name, netboxvm.id, netboxvm.name)
                    netboxipamlanip(openstackip, address_summary, netbox_lan_address_dictionary, netboxvrf)
                else:
                    print(f"Skipping {portid} because it is neither global nor private.")
                    pass
        except Exception as e:
            print(f"Unable to run script to parse IP-addresses to pass to IP-creation script for Interface {portid}")
            print(f"{e}")
            sys.exit(1)
    print(f"Skipped {unchanged_wan_ips} WAN IPs and {unchanged_lan_ips} LAN IPs thus far, because there were no changes.")


def netboxipamfloat(neutronfloatdictionary, neutronsubnetdictionary, netbox_vm_dictionary, netbox_interface_dictionary,
                    netbox_vrf_dictionary, netbox_lan_address_dictionary, netbox_wan_address_dictionary):
    global unchanged_wan_ips
    global unchanged_lan_ips
    # We parse the values in the floating-IP dictionary,
    # and run the Netbox IP-creation functions based on the populated values
    for floatid in neutronfloatdictionary:
        try:
            openstackinstanceid = neutronfloatdictionary[floatid]['boundtoinstanceid']
            openstackfloatip = neutronfloatdictionary[floatid]['floatip']
            openstacktackipstatus = "active"  # It's always N/A in OpenStack for all Floating IPs bound to Instances...
            openstackinterfaceid = neutronfloatdictionary[floatid]['boundtointerfaceid']
            netboxvm = netbox_vm_dictionary.get(openstackinstanceid)
            netboxinterface = netbox_interface_dictionary.get(openstackinterfaceid)
            # TODO find and merge the subnet of a Floating IP somehow
            if ipaddress.ip_address(openstackfloatip).is_global:
                address_summary = CreateAddressObject(openstackfloatip, openstacktackipstatus, netboxinterface.id,
                                                      netboxinterface.name, netboxvm.id, netboxvm.name)
                netboxipamglobalip(openstackfloatip, address_summary, netbox_wan_address_dictionary)
            elif ipaddress.ip_address(openstackfloatip).is_private:
                openstacknetworkid = neutronfloatdictionary[floatid]['boundtonetworkid']
                netboxvrf = netbox_vrf_dictionary.get(openstacknetworkid)
                address_summary = CreateAddressObject(openstackfloatip, openstacktackipstatus, netboxinterface.id,
                                                      netboxinterface.name, netboxvm.id, netboxvm.name)
                netboxipamlanip(openstackfloatip, address_summary, netbox_lan_address_dictionary, netboxvrf)
        except Exception as e:
            print(f"Unable to run script to parse Floating IP-addresses to pass to IP-creation script because of Float ID {floatid}")
            print(f"{e}")
            sys.exit(1)
    print(f"Skipped {unchanged_wan_ips} WAN IPs and {unchanged_lan_ips} LAN IPs in total, because there were no changes.")


def netboxipamglobalip(openstack_ip, address_obj, netbox_wan_dic):
    # We add Global/WAN IPs to the Global VRF, because the addresses should be unique
    try:
        if openstack_ip in netbox_wan_dic.keys():
            # If this unique IP is found but with an incorrect prefix, we update it with the proper one
            # Notably, we don't search using additional parameters, as global addresses should be unique
            # This means if you already have this global IP in Netbox, my script will 'take ownership'and modify it
            # We don't add a NetBox Tag to it either
            netbox_ip = netbox_wan_dic.get(openstack_ip)
            compare_wan_address(address_obj, netbox_ip)
        elif openstack_ip not in netbox_wan_dic.keys():
            # If the IP doesn't exist, we create and associate it
            createglobalipamip(address_obj)
    except Exception as e:
        print(f"Unable to run Global IP creation and updating script \n{e}")
        sys.exit(1)


def netboxipamlanip(unprefixed_ip, address_obj, netbox_lan_dic, netbox_vrf):
    try:
        if unprefixed_ip not in netbox_lan_dic.keys():
            # The IP should at least always be found in NetBox, so we immediately create it!
            createlanipamip(address_obj, netbox_vrf)
        elif unprefixed_ip in netbox_lan_dic.keys():
            netbox_ip = netbox_lan_dic.get(unprefixed_ip)
            if netbox_ip.vrf.id == netbox_vrf.id:
                # Local IPs/Interfaces are never migrated between OpenStack Networks/VRFs,
                # So we should assume the Network on the OpenStack side, is still the same on the NetBox side too
                # If this IP already exists in the VRF we expect it to, we can start comparing
                compare_lan_address(address_obj, netbox_ip)
            elif netbox_ip.vrf.id != netbox_vrf.id:
                # Otherwise, if the IP is in the dictionary but not in the VRF we expect
                # That means the same IP address exists in NetBox but also in different VRF(s),
                # which will have gotten squashed together in our dictionary
                # So we do an API call to check if the object exists in our specific VRF
                if nb.ipam.ip_addresses.get(address=unprefixed_ip, vrf_id=netbox_vrf.id, tag="openstack-api-script") is not None:
                    netbox_ip = nb.ipam.ip_addresses.get(address=unprefixed_ip, vrf_id=netbox_vrf.id, tag="openstack-api-script")
                    compare_lan_address(address_obj, netbox_ip)
                else:
                    # And if we truly could not find it, we create it instead
                    createlanipamip(address_obj, netbox_vrf)
            else:
                # In case the IP exists in multiple VRFs, but not in the VRF we expect it to
                createlanipamip(address_obj, netbox_vrf)
        else:
            print(f"Something weird is happening for lan IP {unprefixed_ip}")
            pass  # In case of 100.64.0.0/10 RFC6598 maybe
    except Exception as e:
        print(f"Unable to run LAN IP creation and updating script \n{e}")
        sys.exit(1)


class CreateAddressObject:
    def __init__(self, prefixed_address, os_status, nb_int_id, nb_int_name, nb_vm_id, nb_vm_name):
        self.address = prefixed_address
        self.status = os_status
        self.nb_int_name = nb_int_name
        self.nb_int_id = nb_int_id
        self.nb_vm_name = nb_vm_name
        self.nb_vm_id = nb_vm_id


def compare_wan_address(os_address_object, nb_addr):
    global unchanged_wan_ips
    try:
        nb_addr_status = str(nb_addr.status)
        nb_addr_status = nb_addr_status.lower()
        if os_address_object.status != nb_addr_status or os_address_object.nb_int_id != nb_addr.assigned_object_id:
            # We are left with updating only 2 useful values: the status and the bound Interface
            updateglobalipamip(os_address_object, nb_addr)
        else:
            unchanged_wan_ips = unchanged_wan_ips + 1
            if (unchanged_wan_ips % 10) == 0:
                print(f"Skipped {unchanged_wan_ips} WAN IPs because nothing changed")
            else:
                pass
            pass
    except Exception as e:
        print(f"Unable to compare global address {print(vars(os_address_object))} state to NetBox \n {nb_addr} \n{e}")
        sys.exit(1)


def compare_lan_address(os_address_object, nb_addr):
    global unchanged_lan_ips
    try:
        nb_addr_status = str(nb_addr.status)
        nb_addr_status = nb_addr_status.lower()
        if os_address_object.status != nb_addr_status or os_address_object.nb_int_id != nb_addr.assigned_object_id:
            # We are left with updating only 2 useful values: the status and the bound Interface
            updatelanipamip(os_address_object, nb_addr)
        else:
            unchanged_lan_ips = unchanged_lan_ips + 1
            if (unchanged_lan_ips % 10) == 0:
                print(f"Skipped {unchanged_lan_ips} LAN IPs because nothing changed")
            else:
                pass
            pass
    except Exception as e:
        print(f"Unable to compare LAN address {print(vars(os_address_object))} state to NetBox \n {nb_addr} {nb_addr.status} \n{e}")
        sys.exit(1)

