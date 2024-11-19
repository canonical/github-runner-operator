# Contributing

You can create an environment for development with `tox`:

```shell
tox devenv -e unit
source venv/bin/activate
```

## Generating src docs for every commit

Run the following command:

```bash
echo -e "tox -e src-docs\ngit add src-docs\n" >> .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Testing

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

```shell
tox run -e format        # update your code according to linting rules
tox run -e lint          # code style
tox run -e unit          # unit tests
tox                      # runs 'format', 'lint', and 'unit' environments
```


<!-- You may want to include any contribution/style guidelines in this document>
