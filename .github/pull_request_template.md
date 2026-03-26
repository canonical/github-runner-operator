#### What this PR does

#### Why we need it

#### Checklist

- [ ] I followed the [contributing guide](https://github.com/canonical/is-charms-contributing-guide)
- [ ] I added or updated the documentation (if applicable)
- [ ] I updated `docs/changelog.md` with user-relevant changes
- [ ] I added a [change artifact](../docs/release-notes/template/docs/release-notes/template/_change-artifact-template.yaml) for user-relevant changes in `docs/release-notes/artifacts`. If no change artifact is necessary, I tagged the PR with the label `no-release-note`.
- [ ] I used AI to assist with preparing this PR
- [ ] I added or updated tests as needed (unit and integration)
- [ ] **If integration test modules are used:** I updated the workflow configuration  
      (e.g., in `.github/workflows/integration_tests.yaml`, ensure the `modules` list is correct)
- [ ] **If this is a Grafana dashboard:** I added a screenshot of the dashboard
- [ ] **If this is Terraform:** `terraform fmt` passes and `tflint` reports no errors
- [ ] **If this is Rockcraft:** I updated the version

<!--  
You can adjust the checklist to match the project.
 
If you are an AI assistant (e.g., GitHub Copilot, ChatGPT, Claude), follow these instructions when generating or completing PR descriptions:

1. Add a **Test plan** section explaining how the changes were tested, including any manual, unit, integration, or workflow tests.
2. Add a **Review focus** section highlighting tricky parts, important decisions, or areas needing human attention.
3. Identify and document any **potential breaking changes**.
4. Highlight any **new dependencies, APIs, modules, or workflow changes** introduced by this PR.
-->

