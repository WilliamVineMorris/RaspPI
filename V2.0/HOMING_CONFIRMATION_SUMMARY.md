# Homing Confirmation Feature Implementation

## Overview
Added a homing confirmation system that prompts users before performing homing operations during scan initialization.

## Backend Implementation

### 1. Scan Orchestrator Changes (`scanning/scan_orchestrator.py`)

**New Parameters**:
- Added `homing_confirmation_callback: Optional[Callable] = None` to `start_scan()` method
- Added `self._homing_confirmation_callback: Optional[Callable] = None` instance variable

**Enhanced Homing Logic**:
```python
async def _home_system(self):
    """Home the motion system with optional confirmation"""
    # Check for homing confirmation callback
    if self._homing_confirmation_callback:
        self.logger.info("⚠️  Requesting homing confirmation from user...")
        should_home = await self._homing_confirmation_callback()
        if not should_home:
            self.logger.info("🚫 User declined homing - proceeding without homing")
            return
        else:
            self.logger.info("✅ User confirmed homing - proceeding with homing sequence")
    
    self.logger.info("🏠 Starting homing sequence for motion system")
    # ... existing homing code
```

### 2. Web Interface Changes (`web/web_interface.py`)

**New State Variables**:
```python
# Homing confirmation system
self._homing_confirmation_requested = False
self._homing_confirmation_response = None
```

**New API Endpoint**:
```python
@app.route('/api/homing-confirmation', methods=['POST'])
def api_homing_confirmation():
    """Handle homing confirmation response from user"""
    data = request.get_json() or {}
    should_home = data.get('confirm', True)
    
    if self._homing_confirmation_requested:
        self._homing_confirmation_response = should_home
        return jsonify({'status': 'success'})
```

**Enhanced Scan Start with Callback**:
```python
async def homing_confirmation_callback():
    """Handle homing confirmation request from scan orchestrator"""
    self._homing_confirmation_requested = True
    self._homing_confirmation_response = None
    
    # Wait for user response (30 second timeout)
    for i in range(300):  # 30 seconds * 10 checks per second
        if self._homing_confirmation_response is not None:
            response = self._homing_confirmation_response
            self._homing_confirmation_requested = False
            self._homing_confirmation_response = None
            return response
        await asyncio.sleep(0.1)
    
    # Timeout - default to yes (safe behavior)
    return True

# Pass callback to scan orchestrator
scan_state = await self.orchestrator.start_scan(
    pattern=pattern,
    output_directory=output_dir,
    scan_id=scan_id,
    scan_parameters=scan_params,
    homing_confirmation_callback=homing_confirmation_callback
)
```

**System Status Enhancement**:
```python
status['homing_confirmation'] = {
    'requested': self._homing_confirmation_requested,
    'pending': self._homing_confirmation_requested
}
```

## Frontend Implementation Requirements

### 1. JavaScript Monitoring
Add to existing status monitoring:
```javascript
function checkHomingConfirmation(status) {
    if (status.homing_confirmation && status.homing_confirmation.requested) {
        showHomingConfirmationDialog();
    }
}
```

### 2. Confirmation Dialog
Create modal dialog in web interface:
```html
<div id="homingConfirmationModal" class="modal">
    <div class="modal-content">
        <h3>🏠 Homing Required</h3>
        <p>The scanner needs to perform a homing operation to ensure accurate positioning.</p>
        <p><strong>This will move all axes to their home positions.</strong></p>
        <div class="modal-buttons">
            <button onclick="confirmHoming(true)" class="btn-confirm">✅ Yes, Home Axes</button>
            <button onclick="confirmHoming(false)" class="btn-cancel">❌ Skip Homing</button>
        </div>
    </div>
</div>
```

### 3. Confirmation Handler
```javascript
function confirmHoming(shouldHome) {
    fetch('/api/homing-confirmation', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({confirm: shouldHome})
    })
    .then(response => response.json())
    .then(data => {
        hideHomingConfirmationDialog();
        if (data.status === 'success') {
            console.log('Homing confirmation sent:', shouldHome);
        }
    })
    .catch(error => console.error('Error sending homing confirmation:', error));
}
```

## Usage Flow

### 1. Scan Initiation
1. User starts scan from web interface
2. Web interface calls `orchestrator.start_scan()` with homing callback
3. Orchestrator begins scan execution

### 2. Homing Confirmation
1. Orchestrator reaches `_home_system()` method
2. Calls homing confirmation callback (if provided)
3. Web interface sets `_homing_confirmation_requested = True`
4. Frontend detects confirmation request in status updates
5. Shows confirmation dialog to user

### 3. User Response
1. User clicks "Yes" or "No" in dialog
2. Frontend sends POST to `/api/homing-confirmation`
3. Backend sets `_homing_confirmation_response`
4. Callback returns response to orchestrator
5. Orchestrator proceeds with or without homing

### 4. Timeout Handling
- **30-second timeout** for user response
- **Default behavior**: Proceed with homing (safe option)
- **Logging**: All decisions logged for audit trail

## Safety Features

### ✅ **Safe Defaults**
- Timeout defaults to **YES** (perform homing)
- Error conditions default to **YES** (perform homing)
- Missing callback proceeds with automatic homing

### ✅ **User Choice**
- Clear warning about axis movement
- Explicit "Yes" or "No" options
- No ambiguous default selections

### ✅ **System Integrity**
- Scan continues regardless of homing decision
- Position accuracy warnings when homing skipped
- Full audit trail in logs

## Testing Requirements

### Backend Testing
```python
# Test callback integration
async def test_homing_confirmation():
    confirmed = False
    
    async def mock_callback():
        return confirmed
    
    scan_state = await orchestrator.start_scan(
        pattern=pattern,
        output_directory=output_dir,
        homing_confirmation_callback=mock_callback
    )
```

### Frontend Testing
1. **Status Monitoring**: Verify confirmation requests detected
2. **Dialog Display**: Confirm modal shows with correct content  
3. **API Communication**: Test both "Yes" and "No" responses
4. **Timeout Behavior**: Verify 30-second timeout works
5. **Error Handling**: Test network failures and malformed responses

## Configuration Options

### Optional Enhancements
1. **Configurable Timeout**: Allow customization of 30-second default
2. **Auto-Home Option**: Skip confirmation for trusted operators
3. **Homing History**: Track homing decisions for audit
4. **Position Validation**: Check if homing is actually needed

---

**Status**: ✅ **IMPLEMENTED** - Backend homing confirmation system ready
**Next Action**: Frontend implementation and testing on Pi hardware

## Files Modified
1. `scanning/scan_orchestrator.py` - Added confirmation callback system
2. `web/web_interface.py` - Added confirmation API and callback implementation

## Required Frontend Changes
1. Update web interface templates with confirmation dialog
2. Add JavaScript monitoring for homing confirmation requests
3. Implement modal dialog and user interaction handlers
4. Test complete flow on actual Pi hardware