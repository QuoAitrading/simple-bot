# License Expiration Timer - Visual Guide

## Location
The license expiration timer is displayed in the **bottom right corner** of the Trading Controls screen (Screen 2).

## Layout
```
┌─────────────────────────────────────────────────────────────┐
│  Trading Controls Screen                                     │
│                                                               │
│  [Account Selection] [Ping Server] [Auto Configure]          │
│  [Symbol Selection: ES, MES, NQ, MNQ]                        │
│  [Trading Parameters: Contracts, Limits, etc.]               │
│  [Confidence Slider]                                          │
│                                                               │
│  ┌──────────┐         ┌───────────────┐      ┌─────────────┐│
│  │ ⚙️        │         │  LAUNCH AI    │      │ ⏱️ License  ││
│  │ Settings │         │               │      │ Expires:    ││
│  └──────────┘         └───────────────┘      │ 10d 5h 30m  ││
│                                               │ 45s         ││
│                                               └─────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Display Format

The timer shows time remaining in the most appropriate format:

### When >1 day remaining:
```
⏱️ License Expires:
10d 5h 30m 45s
```

### When <1 day but >1 hour remaining:
```
⏱️ License Expires:
5h 30m 45s
```

### When <1 hour but >1 minute remaining:
```
⏱️ License Expires:
45m 30s
```

### When <1 minute remaining:
```
⏱️ License Expires:
30s
```

### When expired:
```
⏱️ License Expires:
EXPIRED
```

## Color Coding

The timer text changes color based on time remaining:

- **Green** (success color): More than 7 days remaining
- **Orange** (warning color): 1-7 days remaining
- **Red** (error color): Less than 1 day remaining or EXPIRED

## Update Frequency

The timer updates **every 1 second** to show accurate countdown.

## Technical Details

- **Data Source**: License expiration date is fetched from the API during login
- **Stored in**: `config["license_expiration"]` (ISO format datetime string)
- **Calculation**: Uses Python `datetime` to calculate remaining time
- **Display**: Automatically formats based on time remaining
- **Lifecycle**: Timer starts when trading screen loads, stops when screen changes

## Example Screenshots

### Green (Plenty of Time)
```
⏱️ License Expires:
30d 12h 45m 30s  [Green text]
```

### Orange (Getting Close)
```
⏱️ License Expires:
3d 8h 15m 20s  [Orange text]
```

### Red (Expiring Soon)
```
⏱️ License Expires:
18h 30m 10s  [Red text]
```

### Red (Expired)
```
⏱️ License Expires:
EXPIRED  [Red text]
```

## Benefits

✅ **Always Visible**: Users can see expiration at a glance
✅ **Real-time Updates**: Count down every second
✅ **Color Alerts**: Visual warning as expiration approaches
✅ **Clear Format**: Easy to read days/hours/minutes/seconds
✅ **No Distractions**: Compact display in corner, doesn't interfere with main UI
