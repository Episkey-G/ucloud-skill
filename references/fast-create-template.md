# Fast Create Template

Use this template when the user intent is clearly one of:

- "最便宜"
- "最小配置"
- "默认配置"
- "随便开一台"

This template is generic. It defines the low-freedom workflow for vague create requests. Product-specific defaults still come from injected hints and the API documentation.

Load this file only after the user explicitly agrees to fast-create. Do not load it preemptively for every create request.

## 1. Resolve Path Once

Before doing anything else, confirm the skill root contains:

- `SKILL.md`
- `scripts/route_product.py`
- `scripts/fetch_api_doc.py`
- `scripts/call_api.py`

If not, resolve the absolute path once and reuse it for the whole turn.

## 2. Fixed Sequence

Run the workflow in this order:

1. `route_product.py <product-keyword>`
2. Confirm the user wants fast-create with minimum usable defaults
3. `fetch_api_doc.py <Product> <CreateAction>`
4. Execute only the minimum live lookups required by the injected hints
5. Build params from:
   - API doc required fields
   - injected fast-create defaults
   - user-provided overrides
6. Show confirmation table
7. Execute the create action only after explicit `YES`

If the user declines fast-create, stop using this template and return to the standard create flow.

## 3. Global Rules

- Do not call price APIs unless the user explicitly asks for cost comparison.
- Do not loop through multiple SKUs, images, or regions to prove what is cheapest.
- Do not invent `ImageId`, `ParamGroupId`, `VPCId`, `SubnetId`, `MachineType`, `DiskType`, or region codes.
- Do not retry the same write operation with guessed parameter changes.
- If the product has a fast-create default in `[System Hint]`, use it as the starting point.

## 4. Minimum Live Checks

Only run the live checks needed to turn guessed values into valid values:

- Resource IDs that must come from inventory, such as `ImageId`, `ParamGroupId`, `VPCId`
- Compatibility checks that validate a default SKU, disk type, or zone exactly once
- User selection when multiple valid business resources exist

Do not add extra lookups beyond that minimum set.

## 5. Confirmation Contract

Before creation, always show:

- billing mode
- region and zone if applicable
- product-specific core size parameters
- required dependent resources such as image, parameter group, or network
- whether any secret or password was user-provided or generated

Do not create anything until the user replies with explicit `YES`.

## 6. Product Overlays

Use the generic workflow above, then apply the matching product overlay from injected hints.

### UHost

Minimum live checks:

1. `DescribeImage` for `ImageId`
2. `DescribeAvailableInstanceTypes` exactly once for compatibility

Default starting point from hints:

- `MachineType=O`
- `CPU=1`
- `Memory=1024`
- `Disks=[{"IsBoot":"True","Type":"CLOUD_SSD","Size":20}]`
- `ChargeType=Dynamic` (按量付费)
- `Quantity=0` (按量模式下表示按需、不限时长)

### UDB

Minimum live checks:

1. `DescribeUDBParamGroup` for `ParamGroupId`
2. `DescribeUDBType` if the user did not specify a valid engine/version

Default starting point from hints:

- `DBTypeId=mysql-8.0`
- `MemoryLimit=2000`
- `DiskSpace=20`
- `InstanceMode=Normal`
- `ChargeType=Dynamic`

### AllocateEIP

Minimum live checks:

- Usually none beyond required region/project context

Default starting point from hints:

- `OperatorName=Bgp`
- `Bandwidth=1`
- `PayMode=Bandwidth`
- `ChargeType=Dynamic`

## 7. Failure Handling

When the API rejects the request:

1. Re-open the API doc and rebuild params from required fields
2. Re-run only the lookup tied to the invalid field
3. Explain the correction
4. Re-confirm if the effective configuration changed

Never recover by blind trial-and-error.
