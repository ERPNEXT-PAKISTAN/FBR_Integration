### FBR Integration

FBR Integration

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd ~/frappe-bench
bench get-app https://github.com/ERPNEXT-PAKISTAN/FBR_Integration.git --branch main
bench --site erpnext.local install-app fbr_integration
bench migrate
bench restart
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/fbr_integration
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
