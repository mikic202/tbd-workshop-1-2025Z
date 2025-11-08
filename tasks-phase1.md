IMPORTANT ❗ ❗ ❗ Please remember to destroy all the resources after each work session. You can recreate infrastructure by creating new PR and merging it to master.

![img.png](doc/figures/destroy.png)

1. Authors:

   Group: z4

   Repo: [link](https://github.com/mikic202/tbd-workshop-1-2025Z)

2. Follow all steps in README.md.

3. From avaialble Github Actions select and run destroy on main branch.

4. Create new git branch and:
    1. Modify tasks-phase1.md file.

    2. Create PR from this branch to **YOUR** master and merge it to make new release.

    <!-- ***place the screenshot from GA after succesfull application of release*** -->

    ![img.png](doc/screenshots/destroy_start.png)

    ![img.png](doc/screenshots/all_finished.png)


5. Analyze terraform code. Play with terraform plan, terraform graph to investigate different modules.

    <!-- ***describe one selected module and put the output of terraform graph for this module here*** -->
    We decided to investigate the vertex-ai-workbench module.

    * Graphs:

    ```bash
    cd modules/vertex-ai-workbench
    terraform init
    ```

    ```bash
    terraform graph | dot -Tpng > ../../doc/screenshots/graph_small.png
    ```

    ![img.png](doc/screenshots/vertexai_graph_small.png)

    ```bash
    terraform graph -type=plan | dot -Tpng >  ../../doc/screenshots/graph.png
    ```

    ![img.png](doc/screenshots/vertexai_graph.png)

    * Descripiton

        The smaller graph shows only nodes with datasources and their relations, dependencies. These are the essencials of the infrastructure objects. Plan graph includes also the variables, providers and other resources as well. Its everything that Terraform uses when planning.

        The Vertex-ai-workbench module provides a Google Cloud Vertex AI Workbench Notebook Instance. The module automates the setup of Vertex instance and enables configuration such as project_name, region, network, subnet. This Instance is a managable Jupyter enviroment for data science and machine learning.

        Main resources:

        1. Google Notebook Instance (`google_notebooks_instance.tbd_notebook`) - managed notebook instance.

        2. Google Project Service (`google_project_service.notebooks`) - the service that ensures that the Nootebooks APIs are enabled in the project. It's a prerequisite for creattion of notebook instance.

        3. Google Cloud Storage Bucket (`google_storage_bucket.notebook-conf-bucket`and `oogle_storage_bucket_object.post-startup`) - Creation of the GCP Buckets for storing operational data - configuration files, startup scripts, etc.

        4. IAM binding (`google_storage_bucket_iam_binding.binding` and `google_project_iam_binding.token_creator_role`) - a authorisation, permission and policy management tool.

        5. Google Cloud Data Source (`data.google_project.project`) - retrieval of project metadata.


6. Reach YARN UI

   ***place the command you used for setting up the tunnel, the port and the screenshot of YARN UI here***


7. Draw an architecture diagram (e.g. in draw.io) that includes:
    1. Description of the components of service accounts
    2. List of buckets for disposal

    ***place your diagram here***

8. Create a new PR and add costs by entering the expected consumption into Infracost
For all the resources of type: `google_artifact_registry`, `google_storage_bucket`, `google_service_networking_connection`
create a sample usage profiles and add it to the Infracost task in CI/CD pipeline. Usage file [example](https://github.com/infracost/infracost/blob/master/infracost-usage-example.yml)

   ***place the expected consumption you entered here***

   ***place the screenshot from infracost output here***

9. Create a BigQuery dataset and an external table using SQL

    ORC file was downloaded from:

    <https://github.com/apache/orc/blob/main/examples/TestOrcFile.test1.orc>

    ```sql
    CREATE SCHEMA IF NOT EXISTS `tbd-2025z-318407.tbd_dataset`
    OPTIONS (
    location = 'europe-west1'
    );

    CREATE EXTERNAL TABLE IF NOT EXISTS `tbd-2025z-318407.tbd_dataset.tab-ext`
    OPTIONS (
    format = 'ORC',
    uris = ['gs://tbd-2025z-318407-data/data/*.orc']
    );
    ```

    Sample query from created table:

    ![img.png](doc/screenshots/bigquery-select.png)


    <!-- ***why does ORC not require a table schema?*** -->
    ORC file type does not require any table schema because it is self-describing. It stores metadata such as column names, data types and structure so reader in bigquery can apply ORC file automatically.


10. Find and correct the error in spark-job.py

    <!-- ***describe the cause and how to find the error*** -->
    After changing the *DATA_BUCKET* in `spark-job.py` the job runned succesfully.

    ![img.png](doc/screenshots/airflow.png)


11. Add support for preemptible/spot instances in a Dataproc cluster

```
resource "google_dataproc_cluster" "tbd-dataproc-cluster" {
  #checkov:skip=CKV_GCP_91: "Ensure Dataproc cluster is encrypted with Customer Supplied Encryption Keys (CSEK)"
  ...

  cluster_config {
    staging_bucket = google_storage_bucket.dataproc_staging.name
    temp_bucket    = google_storage_bucket.dataproc_temp.name

    ...

    preemptible_worker_config {
      num_instances = 0
    }
}
```

[PLIK](modules/dataproc/main.tf)

12. Triggered Terraform Destroy on Schedule or After PR Merge. Goal: make sure we never forget to clean up resources and burn money.

Add a new GitHub Actions workflow that:
  1. runs terraform destroy -auto-approve
  2. triggers automatically:
 
   a) on a fixed schedule (e.g. every day at 20:00 UTC)
 
   b) when a PR is merged to main containing [CLEANUP] tag in title

Steps:
  1. Create file .github/workflows/auto-destroy.yml
  2. Configure it to authenticate and destroy Terraform resources
  3. Test the trigger (schedule or cleanup-tagged PR)

```yaml
name: Destroy-auto-approve
on:
  schedule:
    - cron: "0 20 * * *"
  pull_request:
    types: [closed]
    branches:
      - master
      - main

permissions: read-all
jobs:
  destroy-release:
    if: |
      github.event_name == 'schedule' ||
      (github.event.pull_request.merged == true &&
       github.base_ref == 'main' &&
       contains(github.event.pull_request.title, '[CLEANUP]'))

    runs-on: ubuntu-latest

    permissions:
      contents: write
      id-token: write
      pull-requests: write
      issues: write

    steps:
    - uses: 'actions/checkout@v3'
    - uses: hashicorp/setup-terraform@v2
      with:
        terraform_version: 1.11.0
    - id: 'auth'
      name: 'Authenticate to Google Cloud'
      uses: 'google-github-actions/auth@v1'
      with:
        token_format: 'access_token'
        workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER_NAME }}
        service_account: ${{ secrets.GCP_WORKLOAD_IDENTITY_SA_EMAIL }}
    - name: Terraform Init
      id: init
      run: terraform init -backend-config=env/backend.tfvars
    - name: Terraform Destroy
      id: destroy
      run: terraform destroy -no-color -var-file env/project.tfvars -auto-approve
      continue-on-error: false
```

![alt text](doc/screenshots/auto_destroy.png)

Running auto-destroy helps keeping the servers clean and minimizes the costs for the enterprise.
