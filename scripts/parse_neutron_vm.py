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

from scripts.netbox.create import createnetboxrouter
from scripts.netbox.create import createnetboxagent

from scripts.netbox.update import updatenetboxrouter
from scripts.netbox.update import updatenetboxagent

from scripts.openstack.checkstatus import getstatus

import sys

import settings
keystone = settings.keystone
cluster_name = settings.cluster_name

skippedneutronrouters = 0
skippedneutrondhcp = 0


def neutronrouter_to_netboxvms(neutronrouters, flavordictionary, tenantdictionary, netbox_vm_dictionary):
    global skippedneutronrouters
    for router in neutronrouters:
        routerid = neutronrouters[router]['id']
        tenantid = neutronrouters[router]['tenantid']
        openstackstatus = neutronrouters[router]['status']
        name = neutronrouters[router]['name']
        name = f"Router_{name}"
        name = name[:53] + "_[" + tenantid[:8] + "]"  # Netbox wants unique names per cluster, so it will get it...!
        name = name[:64]
        if tenantdictionary == "none":
            # This is where we attempt fetching Keystone information for the last time
            # but only if collectopenstackinformation() didn't populate tenantdictionary properly
            try:
                tenantname = keystone.projects.get(tenantid)  # We fetch Tenant name via Keystone call
                tenantname = tenantname.name
            except Exception as e:
                print(f"Unable to access OpenStack Keystone tenant name for router {router} via Keystone API call \n{e}")
                tenantname = "Unknown"
                pass
        elif tenantdictionary != "none":
            # If tenantdictionary is properly defined, we fetch the Tenant name from it
            try:
                tenantname = tenantdictionary[tenantid]['name']
            except Exception as e:
                print(f"Skipping Tenantname for router {router}, via dictionary search.")
                print(f"The router may be unassigned to a Tenant, or assigned to a Tenant that does not exist: \n{e}")
                tenantname = "Unknown"
                pass
        else:
            print(f"Unable to access Keystone Project name for router {router}")
            sys.exit(1)
        try:
            status = getstatus(openstackstatus)  # We transform OpenStack statusses to Netbox statusses
        except Exception as e:
            print(f"Unable to transform OpenStack status to Netbox status for router \n{e}")
            sys.exit(1)
        if routerid in netbox_vm_dictionary.keys():
            # Update the Netbox VM info if the Router ID is found in the Netbox-cluster, with the values we prepared
            netbox_vm = netbox_vm_dictionary.get(routerid)
            netbox_vm_status = str(netbox_vm.status)
            netbox_vm_status = netbox_vm_status.lower()
            if (netbox_vm.name != name or
                    netbox_vm_status != status):
                # We perform a comparison of states before we throw stuff at NetBox
                updatenetboxrouter(netbox_vm.id, name, status)
            else:
                skippedneutronrouters = skippedneutronrouters + 1
                if (skippedneutronrouters % 10) == 0:
                    print(f"Skipped {skippedneutronrouters} Neutron Routers because nothing changed")
                else:
                    pass
                continue
        elif routerid not in netbox_vm_dictionary.keys():
            # We create the Netbox VM based on the router, if we couldn't find its ID in Netbox.
            createnetboxrouter(name, status, routerid, tenantname)
    print(f"Skipped {skippedneutronrouters} Neutron Routers in total, because there were no changes.")


def neutrondhcp_to_netboxvms(agentdictionary, netbox_vm_dictionary):
    global skippedneutrondhcp
    for neutronserver in agentdictionary:
        name = agentdictionary[neutronserver]['hostname']
        name = f"Neutronserver_{name}"
        name = name[:64]
        agentid = agentdictionary[neutronserver]['id']
        if agentid in netbox_vm_dictionary.keys():
            # Update the Netbox VM info if its OpenStack ID is found in the Netbox-cluster, with the values we prepared
            netbox_vm = netbox_vm_dictionary.get(agentid)
            if netbox_vm.name != name:
                # The only thing we can possibly update is the name, so we skip it, if it is the same
                # Not like you're going to change the ID of your Neutron server, haha
                updatenetboxagent(netbox_vm.id, name)
            else:
                skippedneutrondhcp = skippedneutrondhcp + 1
                if (skippedneutrondhcp % 10) == 0:
                    print(f"Skipped {skippedneutrondhcp} Neutron DHCP servers because nothing changed")
                else:
                    pass
                continue
        elif agentid not in netbox_vm_dictionary.keys():
            # We create a Neutron Netbox VM if we couldn't find it in Netbox.
            createnetboxagent(name, agentid)
    print(f"Skipped {skippedneutrondhcp} Neutron DHCP servers in total, because there were no changes.")
