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

from scripts.netbox.create import createvmdisk
from scripts.netbox.update import updatevmdisk

import settings
cluster_name = settings.cluster_name

unchangedvols = 0


def cinder_to_netboxdisks(cinderdictionary, netbox_volume_dictionary, netbox_vm_dictionary):
    global unchangedvols
    for volumeid in cinderdictionary.keys():
        try:
            osvolumename = cinderdictionary[volumeid]['osvolname']
            osvolumecustomname = osvolumename[:52] + "_[" + volumeid[:8] + "]"
            os_cinder_vol = CreateCinderVolumeObject(volumeid,
                                                     osvolumename,
                                                     osvolumecustomname,
                                                     cinderdictionary[volumeid]['osvolinstanceid'],  # Bound Instance ID
                                                     cinderdictionary[volumeid]['osvolsizegb'],
                                                     cinderdictionary[volumeid]['osvolsizemb'])
            netboxvm = netbox_vm_dictionary.get(cinderdictionary[volumeid]['osvolinstanceid'])
        except Exception as e:
            print(f"Unable to define variables for Volume {volumeid} \n{e}")
            sys.exit(1)
        try:
            if volumeid in netbox_volume_dictionary.keys():
                # If the disk ID is found in Netbox, we update said Volume
                netboxdisk = netbox_volume_dictionary.get(volumeid)
                compare_vol_objects(os_cinder_vol, netboxdisk, netboxvm)
            elif volumeid not in netbox_volume_dictionary.keys():
                # If the Volume is not found, we create a Netbox Volume and attach it
                createvmdisk(os_cinder_vol, netboxvm)
        except Exception as e:
            print(f"Unable to create or update OpenStack Volume {osvolumename} \n{e}")
            print(vars(os_cinder_vol))
            sys.exit(1)
    print(f"Skipped {unchangedvols} Virtual Disks because their state hasn't changed.")


class CreateCinderVolumeObject(object):
    def __init__(self, os_vol_id, os_vol_name, vol_custom_name, os_vol_instance_id, os_vol_gb, os_vol_mb):
        self.vol_id = os_vol_id
        self.vol_name = os_vol_name
        self.custom_name = vol_custom_name
        self.instance_id = os_vol_instance_id
        self.vol_gb = os_vol_gb
        self.vol_mb = os_vol_mb


def compare_vol_objects(os_cinder_vol_obj, nb_vol, nb_vm):
    global unchangedvols
    try:
        if (nb_vol.size != os_cinder_vol_obj.vol_mb or
                (nb_vol.name != os_cinder_vol_obj.vol_name and nb_vol.name != os_cinder_vol_obj.custom_name) or
                nb_vol.virtual_machine.id != nb_vm.id):
            updatevmdisk(os_cinder_vol_obj, nb_vm, nb_vol)
        else:
            # If nothing changed, we skip updating the Volume
            unchangedvols = unchangedvols + 1
            if (unchangedvols % 10) == 0:
                print(f"Skipped {unchangedvols} NetBox Virtual Disks because nothing changed")
            pass
    except Exception as e:
        print(f"Unable to compare states for Virtual Disk {os_cinder_vol_obj} \n{e}")
        print(vars(os_cinder_vol_obj))
        sys.exit(1)
