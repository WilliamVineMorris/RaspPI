# YOLO Detection Array Comparison Fix

## Error Fixed
```
ValueError: The truth value of an array with more than one element is ambiguous. Use a.any() or a.all()
```

## Root Cause
Line 205 in `camera/yolo11n_detector.py`:
```python
marker = "→" if cand == best else " "
```

The comparison `cand == best` failed because both `cand` and `best` are dictionaries containing NumPy arrays (the `bbox` field). Python can't directly compare dictionaries with arrays.

## Fix Applied
Added an `index` field to each candidate and compare using that:

```python
# BEFORE (broken):
candidates.append({
    'bbox': bbox,
    'confidence': conf,
    ...
})
marker = "→" if cand == best else " "  # ❌ Fails with NumPy arrays

# AFTER (fixed):
candidates.append({
    'index': i,  # Add unique index
    'bbox': bbox,
    'confidence': conf,
    ...
})
marker = "→" if cand['index'] == best['index'] else " "  # ✅ Works!
```

## Test Now
```bash
python3 test_yolo_detection.py --with-camera
```

Should now work without the ValueError!

---

**Status**: ✅ Fixed  
**File Modified**: `camera/yolo11n_detector.py` (line 187 and 205)
