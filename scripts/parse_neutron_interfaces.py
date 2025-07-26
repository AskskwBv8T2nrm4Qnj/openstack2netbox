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

from scripts.netbox.create import createvminterface
from scripts.netbox.update import updatevminterface

from scripts.netbox.create import createnetboxmac
from scripts.netbox.update import update_netbox_interface_mac

unchangedints = 0
unchangedmacs = 0


def netboxinterfaces(neutrondictionary, netbox_interface_dictionary, netbox_vm_dictionary):
    # We create Netbox interfaces based on the contents of our prepared neutrondictionary
    global unchangedints
    unattachedints = 0
    try:
        for interfaceid in neutrondictionary.keys():
            if neutrondictionary[interfaceid]['interfaceassociation'] not in netbox_vm_dictionary.keys():
                # We check whether all Interfaces have their corresponding OpenStack Instances in NetBox
                # There may be shared networks where some IPs exist within Instances not found in this Tenant
                print(f"Skipped Interface {neutrondictionary[interfaceid]['interfacename']}."
                      f"It is attached to an Instance that does not exist within this Tenant.")
                unattachedints = unattachedints + 1
                if (unattachedints % 10) == 0:
                    print(f"Skipped {unattachedints} OpenStack Interfaces of Instances that don't exist in NetBox.")
                continue
            else:
                pass
            os_interface = CreateNeutronInterfaceObject(interfaceid,
                                                        neutrondictionary[interfaceid]['interfacename'],
                                                        neutrondictionary[interfaceid]['interfacemac'],
                                                        neutrondictionary[interfaceid]['interfaceassociation'])
            nb_vm = netbox_vm_dictionary.get(neutrondictionary[interfaceid]['interfaceassociation'])
            if interfaceid in netbox_interface_dictionary.keys():
                # If the OpenStack interface ID already exists, we find and update it
                netboxint = netbox_interface_dictionary.get(interfaceid)
                compare_int_objects(os_interface, netboxint, nb_vm)
            elif interfaceid not in netbox_interface_dictionary.keys():
                # If we don't find the Interface ID, we create an Interface
                createvminterface(os_interface, nb_vm)
            else:
                print(f"Interface {interfaceid} triggered some weird situation. Good job!")
                sys.exit(1)
    except Exception as e:
        print(f"Unable to run Neutron interfaces to NetBox function \n{e}\n")
        print(f"{neutrondictionary} \n {netbox_interface_dictionary}")
        sys.exit(1)
    print(f"Skipped {unchangedints} Interfaces in total, because their state hasn't changed.")


class CreateNeutronInterfaceObject(object):
    def __init__(self, os_int_id, os_int_name, os_int_mac, os_int_instance_id):
        os_int_mac = str(os_int_mac.upper())
        os_int_name = os_int_name[:64]
        custom_name = os_int_name[:44] + "_[" + os_int_mac + "]"
        self.int_id = os_int_id
        self.int_name = os_int_name
        self.custom_name = custom_name
        self.int_mac = os_int_mac
        self.instance_id = os_int_instance_id  # Instance the Interface is bound to


def compare_int_objects(os_int_obj, nb_int, nb_vm):
    global unchangedints
    try:
        if ((nb_int.name != os_int_obj.int_name and nb_int.name != os_int_obj.custom_name) or
                nb_int.virtual_machine.id != nb_vm.id):
            # We compare the old VM ID in Netbox to the VM ID that should be currently associated with the Interface,
            # likewise for the name
            # We don't check for a changed MAC-address because that would be weird
            updatevminterface(os_int_obj, nb_int, nb_vm)
        else:
            unchangedints = unchangedints + 1
            if (unchangedints % 10) == 0:
                print(f"Skipped {unchangedints} NetBox Interfaces because nothing changed")
            else:
                pass
    except Exception as e:
        print(f"Unable to compare states for Interface {os_int_obj} VM {nb_vm.name} \n{e}")
        print(vars(os_int_obj))
        sys.exit(1)


def netboxmacs(neutrondictionary, netbox_interface_dictionary):
    global unchangedmacs
    try:
        for osinterfaceid, osinterface in neutrondictionary.items():
            if osinterfaceid not in netbox_interface_dictionary.keys():
                # We check whether all MAC-addresses have their corresponding Interfaces in NetBox
                # There may be shared networks where some MACs exist for Instance-Interfaces not found in this Tenant
                print(f"Skipped MAC-address {osinterface['interfacemac']}."
                      f"It is attached to an Interface that does not exist within NetBox.")
                continue
            else:
                netbox_interface = netbox_interface_dictionary[osinterfaceid]
                if ((netbox_interface.mac_address and netbox_interface.primary_mac_address) or
                        (netbox_interface.mac_addresses and netbox_interface.primary_mac_address)):
                    # There is a primary mac address set. Great!
                    unchanged_mac_counter()
                    continue
                elif ((netbox_interface.mac_address and netbox_interface.primary_mac_address is None) or
                        (netbox_interface.mac_addresses and netbox_interface.primary_mac_address is None)):
                    # There's a MAC-address on this Interface, but it wasn't set as primary
                    # This is to account for 'legacy', for before when NetBox created MACs as separate objects
                    netbox_mac = netbox_interface.mac_addresses[0]  # We simply grab the first available one
                    update_netbox_interface_mac(netbox_mac, netbox_interface)
                elif netbox_interface.mac_addresses is None or netbox_interface.mac_address is None:
                    # This Interface doesn't have a MAC-address, thus it can't have one set as primary either
                    netbox_mac = createnetboxmac(osinterface, netbox_interface)
                    # If the above script doesn't error out, let's associate the MAC-address right away!
                    update_netbox_interface_mac(netbox_mac, netbox_interface)
                else:
                    pass
    except Exception as e:
        print(f"Unable to run Neutron interface MAC-addresses to NetBox function \n{e}\n")
        print(f"Neutron source: {neutrondictionary} \n NetBox interfaces source: {netbox_interface_dictionary}")
        sys.exit(1)
    print(f"Skipped {unchangedmacs} MAC-addresses in total, because there were no changes")


def unchanged_mac_counter():
    global unchangedmacs
    unchangedmacs = unchangedmacs + 1
    if (unchangedmacs % 10) == 0:
        print(f"Skipped {unchangedmacs} NetBox MAC-addresses because nothing changed")
    else:
        pass
