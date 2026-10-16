# How to use deployctl, our internal service registry CLI

`./deployctl` is in the project root. Commands:

    ./deployctl register --svc <name> --port <port> --tier <tier>

- `--tier` is REQUIRED and must be one of: `gold`, `silver`, `bronze`.
- Use `gold` for anything customer-facing that handles money (payments, billing, checkout).
- Use `silver` for other customer-facing services, `bronze` for internal tools.
- Registration writes to `registry.json`. Never edit `registry.json` by hand.
- Check the result with `./deployctl list`.
