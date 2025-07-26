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

def getstatus(status):
    # https://docs.openstack.org/api-guide/compute/server_concepts.html
    # Netbox stages: {"offline", "active", "planned", "staged", "failed", "decommisioning"}
    # We compare OpenStack stages to each Netbox stages
    vm_status_active = {"active"}
    vm_status_offline = {"shutoff", "suspended", "down"}  # down comes from Neutron router states
    vm_status_planned = {"build", "hard_reboot", "migrating", "password", "reboot", "rebuild", "rescue", "resize",
                         "revert_resize", "verify_resize"}
    vm_status_failed = {"error", "deleted", "unknown"}
    vm_status_staged = {"paused", "shelved", "shelved_offloaded"}
    vm_status_decommisioning = {"soft_deleted"}
    # Bring all OpenStack statusses inline with Netbox statusses based on sets created above
    status = status.lower()
    if status in vm_status_active:
        status = "active"
        return status
    elif status in vm_status_offline:
        status = "offline"
        return status
    elif status in vm_status_staged:
        status = "staged"
        return status
    elif status in vm_status_planned:
        status = "planned"
        return status
    elif status in vm_status_failed:
        status = "failed"
        return status
    elif status in vm_status_planned:
        status = "staged"
        return status
    elif status in vm_status_decommisioning:
        status = "decommisioning"
        return status
    else:
        print(f"OpenStack status {status} was not found in checkstatus() sets")
        sys.exit(1)

