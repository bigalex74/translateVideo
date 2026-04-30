# Pipeline

The pipeline package coordinates provider-neutral stages. It records stage runs
and artifacts through `ProjectStore`, which allows CLI, UI, and future webhooks
to resume or inspect jobs consistently.
