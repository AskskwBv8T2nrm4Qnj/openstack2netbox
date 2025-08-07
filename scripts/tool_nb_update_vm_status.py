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

sys.path.insert(1, os.path.join(sys.path[0], '..'))
import settings
nb = settings.nb
cluster_name = settings.cluster_name

from openstack.checkstatus import getstatus
from openstack.fetchinfo import get_nova
from netbox.fetchinfo import nbfetchvms

try:
    print(f'\nFetching information from OpenStack \n')
    myinstances, nova_flavor_dictionary = get_nova()
    print(f'Finished fetching information from OpenStack. \n')
except Exception as e:
    print(f"Unable to collect information from OpenStack \n{e}")
    sys.exit(1)

try:
    print(f'Fetching information from NetBox for cluster {cluster_name}\n')
    netboxvmdic = nbfetchvms()
    print(f'\nFinished collecting information from NetBox for cluster {cluster_name}')
except Exception as e:
    print(f"Unable to collect information from NetBox \n{e}")
    sys.exit(1)


def updatestatus(nova_instances, netbox_vm_dictionary):
    unchangedvms = 0
    print(f"Attempting to update Netbox Virtual Machine statuses for Netbox cluster {cluster_name}")
    for instance in nova_instances:
        currentstatus = getstatus(instance.status)  # We transform OpenStack statuses to Netbox statuses
        if instance.id in netbox_vm_dictionary.keys():
            nbvm = netbox_vm_dictionary.get(instance.id)
            nbvmvstatus = str(nbvm.status)
            nbvmvstatus = nbvmvstatus.lower()
            if nbvmvstatus == currentstatus:
                # Status was unchanged, so we skip it
                # print(f"Skipping {instance.name}")
                unchangedvms = unchangedvms + 1
                if (unchangedvms % 10) == 0:
                    print(f"Update: {unchangedvms} VMs were skipped because nothing changed...")
                pass
            elif nbvmvstatus != currentstatus:
                # The status is different now, so we update it!
                try:
                    # Update the Netbox VM info if its OpenStack ID is found in the Netbox-cluster, with the new status
                    updatenetboxvmstatus(nbvm.id, currentstatus)
                    print(f"The status of {instance.name} in Netbox cluster {cluster_name} was updated")
                except Exception as e:
                    print(f"Unable to update the status of {instance.name} in Netbox cluster {cluster_name} \n{e}")
                    sys.exit(1)
        else:
            print(f"Skipping VM {instance.name}, its OpenStack ID was not found in the Netbox cluster. ID: {instance.id}")
            continue
    print(f"\nThe script finished succesfully.")
    print(f"{unchangedvms} VMs were skipped because their status hasn't changed.")


def updatenetboxvmstatus(netbox_vm_id, status):
    # Update OpenStack VM in Netbox based on given values
    vm = nb.virtualization.virtual_machines.update([
        {'id': netbox_vm_id, 'status': status}
    ])


updatestatus(myinstances, netboxvmdic)
