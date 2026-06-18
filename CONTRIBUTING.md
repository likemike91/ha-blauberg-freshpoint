# Contributing

Thanks for improving the Blauberg Freshpoint integration.

## Local Checks

Run these before opening a pull request:

```bash
python3 -m py_compile custom_components/freshpoint/*.py freshpoint_probe.py freshpoint_mqtt_bridge.py
python3 -m json.tool hacs.json >/dev/null
python3 -m json.tool custom_components/freshpoint/manifest.json >/dev/null
python3 -m json.tool custom_components/freshpoint/strings.json >/dev/null
```

## Pull Requests

Please include:

- the Freshpoint model tested
- whether discovery worked
- Home Assistant version
- logs for connection or protocol errors

Avoid adding external dependencies unless the integration cannot reasonably work without them.
