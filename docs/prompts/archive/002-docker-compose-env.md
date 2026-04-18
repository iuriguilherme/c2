/taches-cc-resources:create-prompt

The environments are hard coded on docker-compose.yml and repeating.
We need a single source of thruth.
There is no sensitive information so those can come from a version control mantained (not gitignored) file used as env_file for all images.
Meaning we can move OLLAMA_MODEL_DIR to that new file too.
