# 🚨 REVERT: Lens Inversion "Fix" Was Wrong!

## What Happened

I incorrectly "fixed" what I thought was a lens inversion bug, but **the original code was correct for your hardware!**

## The Mistake

**What I thought:** The lens mapping was inverted (0.5 → lens 511 was wrong)
**Reality:** The lens mapping WAS correct (0.5 → lens 511 was right)

Your observation "increasing focus makes closer objects sharp" was actually **correct behavior** but I misinterpreted it!

## What Was Reverted

All lens position calculations in `camera/pi_camera_controller.py` and `scanning/scan_orchestrator.py`:

**REVERTED TO (CORRECT):**
```python
lens_position = int((1.0 - focus_value) * 1023)  # ✅ CORRECT
```

**What I incorrectly changed to:**
```python
lens_position = int(focus_value * 1023)  # ❌ WRONG
```

## What Was KEPT (Still Good)

✅ **Dashboard focus conversion** - This fix is still valid and needed:
```python
# Convert dashboard 6-10mm to lens 0-1023
focus_mm = float(controls_dict['focus_position'])
focus_normalized = (focus_mm - 6.0) / 4.0
lens_position = int((1.0 - focus_normalized) * 1023)
```

✅ **AfRange = Full for manual focus** - Allows full lens travel range

## Current State

**Dashboard focus now works correctly:**
- 6.0mm → normalized 0.0 → lens 1023 (near)
- 8.0mm → normalized 0.5 → lens 511 (middle)  
- 10.0mm → normalized 1.0 → lens 0 (far)

**Scan focus (uses same conversion):**
- Web UI 8mm → normalized 0.5 → lens 511

## Testing

Please restart and test:
```bash
sudo systemctl restart scanner
```

The dashboard slider should now work across the full range (6-10mm) and produce sharp focus at the expected distances!

---

**Apologies for the confusion!** The lens WAS working correctly before. The only real bug was the dashboard not converting 6-10mm values properly.
