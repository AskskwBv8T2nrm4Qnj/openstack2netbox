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

import settings
nb = settings.nb
cluster_name = settings.cluster_name

# Requirements
# Netbox Cluster must be associated to the physical site!
# Netbox Physical Devices must be associated to the cluster!

nodedictionary = {"host1": "myphysicalserver123994", "host2": "myphysicalserver712", "host3": "myphysicalserver55"}


def updatehypervisor(netboxserverid, physicalserverid):
    # Update OpenStack VM device field in Netbox based on given value
    vm = nb.virtualization.virtual_machines.update([
        {'id': netboxserverid,
         'device': physicalserverid
         }
    ])


def tryhypervisor():
    try:
        for server in nb.virtualization.virtual_machines.filter(cluster=cluster_name, tag="openstack-api-script"):
            if server.custom_fields["openstack_hypervisor"] in nodedictionary.keys():
                # If the value in the field is a key in nodedictionary, we continue
                physicalservername = nodedictionary[server.custom_fields["openstack_hypervisor"]]
                # We match the value by referencing the given dictionary key
                try:
                    physicalserverid = nb.dcim.devices.get(name=physicalservername).id
                    # We get the Netbox Device ID by using the dictionary value
                    # print(server.name, physicalservername, physicalserverid, server.id)
                    updatehypervisor(server.id, physicalserverid)
                    print(f"Updated Netbox VM: {server.name} ID: {server.id} in cluster {cluster_name} "
                          f"with hypervisor {physicalservername}")
                except Exception as e:
                    print(f"Device {physicalservername} does not exist in Netbox or is duplicate: {e}")
            else:
                print(f"Device {server.custom_fields['openstack_hypervisor']} of {server} does not exist in dictionary")
                continue
    except Exception as e:
        print(f"Unable to update Netbox hypervisor field \n{e}")


tryhypervisor()
