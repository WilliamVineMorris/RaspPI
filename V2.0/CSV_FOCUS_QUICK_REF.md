# CSV Focus Control Quick Reference

## CSV Format

### Required Columns
```
index,x,y,z,c
```

### Optional Focus Columns
```
FocusMode,FocusValues
```

## Focus Mode Values

| CSV Value | Meaning | Use FocusValues? |
|-----------|---------|------------------|
| `manual` | Manual lens position | ✅ Required |
| `af` | Autofocus once | ❌ Ignored |
| `ca` | Continuous autofocus | ❌ Ignored |
| `default` | Use global config | ❌ Ignored |
| `` (empty) | Use global config | ❌ Ignored |

## Focus Values Format

### Single Position
```csv
FocusMode,FocusValues
manual,8.0
```

### Multiple Positions (Focus Stacking)
```csv
FocusMode,FocusValues
manual,"6.0;8.0;10.0"
```

**Note**: Use semicolons (`;`) to separate multiple values

## Lens Position Range

- **Minimum**: 0.0 (infinity)
- **Maximum**: 15.0 (close-up)
- **Typical macro**: 6.0 - 10.0

## Example CSVs

### Simple Manual Focus
```csv
index,x,y,z,c,FocusMode,FocusValues
0,100,100,0,0,manual,8.0
1,100,100,45,0,manual,8.0
2,100,100,90,0,manual,8.0
```

### Focus Stacking (3 Positions)
```csv
index,x,y,z,c,FocusMode,FocusValues
0,100,100,0,0,manual,"6.0;8.0;10.0"
1,100,100,45,0,manual,"6.0;8.0;10.0"
2,100,100,90,0,manual,"6.0;8.0;10.0"
```

### Mixed Modes
```csv
index,x,y,z,c,FocusMode,FocusValues
0,100,100,0,0,af,
1,100,100,45,0,manual,8.0
2,100,100,90,0,manual,"6.0;8.0;10.0"
3,100,100,135,0,,
```

### Backward Compatible (No Focus)
```csv
index,x,y,z,c
0,100,100,0,0
1,100,100,45,0
2,100,100,90,0
```
**Result**: Uses global config default

## Common Patterns

### Dragon Photography (Close-up)
```csv
index,x,y,z,c,FocusMode,FocusValues
0,100,100,0,0,manual,"7.0;8.0;9.0"
```
**Use**: 3 focus planes for depth-of-field stacking

### Coin Scanning (Flat Object)
```csv
index,x,y,z,c,FocusMode,FocusValues
0,100,100,0,0,manual,8.0
```
**Use**: Single focus - object is flat

### Variable Height Object
```csv
index,x,y,z,c,FocusMode,FocusValues
0,100,100,0,0,manual,8.0
1,100,100,45,0,manual,7.5
2,100,100,90,0,manual,8.5
3,100,100,135,0,manual,8.0
```
**Use**: Adjust focus per angle for uneven surfaces

## Performance Tips

✅ **DO**: Use focus stacking for 3-5 positions at same point  
❌ **DON'T**: Create separate scans - 62% slower!

✅ **DO**: Use manual focus when possible - instant  
❌ **DON'T**: Use autofocus for every point - 4s per point

✅ **DO**: Group similar focus values together  
❌ **DON'T**: Mix focus modes randomly - inefficient

## Validation Errors

### Invalid Focus Mode
```csv
index,x,y,z,c,FocusMode,FocusValues
0,100,100,0,0,bad_mode,8.0
```
❌ Error: `Invalid focus mode 'bad_mode'`

### Out of Range
```csv
index,x,y,z,c,FocusMode,FocusValues
0,100,100,0,0,manual,20.0
```
❌ Error: `Focus value 20.0 exceeds range [0.0, 15.0]`

### Invalid Format
```csv
index,x,y,z,c,FocusMode,FocusValues
0,100,100,0,0,manual,abc
```
❌ Error: `Invalid focus values format`

## Warnings

### Autofocus with Values
```csv
index,x,y,z,c,FocusMode,FocusValues
0,100,100,0,0,af,8.0
```
⚠️ Warning: `Focus values ignored when using autofocus mode 'af'`

### Too Many Positions
```csv
index,x,y,z,c,FocusMode,FocusValues
0,100,100,0,0,manual,"4.0;5.0;6.0;7.0;8.0;9.0;10.0"
```
⚠️ Warning: `7 focus positions will significantly increase scan time`

## File Locations

### Example Files
- `examples/simple_manual_focus.csv`
- `examples/focus_stacking_3_positions.csv`
- `examples/mixed_focus_modes.csv`
- `examples/backward_compatible_no_focus.csv`

### Documentation
- `CSV_FOCUS_PARSER_UPDATE.md` - Complete implementation guide
- `PER_POINT_FOCUS_CONTROL.md` - User guide
- `WEB_UI_FOCUS_INTEGRATION.md` - Web UI integration

## Testing

Run test suite:
```bash
cd RaspPI/V2.0
python test_csv_focus_parsing.py
```

## Support

- ✅ FluidNC format (x, y, z, c)
- ✅ Camera-relative format (radius, height, rotation, tilt)
- ✅ Cartesian format (x, y, z, c)
- ✅ Backward compatible with old CSVs
- ✅ Focus stacking (multiple captures per point)
- ✅ Mixed focus modes in same scan
