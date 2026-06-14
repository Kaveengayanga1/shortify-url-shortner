# Shortify — Serverless URL Shortener

A fully serverless URL shortener on AWS. Create a short code for any `http`/`https`
link and get redirected to the original URL, with per-link click counting. The
entire stack — compute, storage, routing, and state — is managed with Terraform
and runs on pay-per-request, scale-to-zero AWS services.

> Scope: **create + redirect** only. QR-code generation is planned for a later
> iteration.

---

## Tech Stack

| Layer            | Technology                                              |
| ---------------- | ------------------------------------------------------- |
| Compute          | AWS Lambda (Python 3.13)                                 |
| API / Routing    | Amazon API Gateway (HTTP API, v2)                       |
| Storage          | Amazon DynamoDB (single-table, on-demand)               |
| Infrastructure   | Terraform (`>= 1.5`, AWS provider `~> 5.0`)             |
| Remote State     | S3 (versioned + encrypted) with DynamoDB state locking  |
| Observability    | CloudWatch Logs, optional AWS X-Ray tracing             |
| Testing          | pytest + moto (mocked AWS)                               |
| SDK              | boto3 (provided by the Lambda runtime)                  |

---

## Architecture

```
                 ┌──────────────────────────────────────────────┐
   POST /urls    │              API Gateway (HTTP API)          │
 ───────────────▶│                                              │
   { "url": … }  │   POST /urls  ──▶  create  Lambda            │
                 │   GET  /{code} ─▶  redirect Lambda           │
   GET /{code}   │                                              │
 ───────────────▶│                                              │
   302 redirect  └───────────────┬──────────────┬───────────────┘
                                 │              │
                      PutItem    │              │  GetItem / UpdateItem
                                 ▼              ▼
                 ┌──────────────────────────────────────────────┐
                 │          DynamoDB: shortify-urls              │
                 │  PK = SHORT#<code>   SK = META                │
                 │  GSI1 = OWNER#<owner> (list links by owner)   │
                 │  TTL  = expiresAt (auto-expire links)         │
                 └──────────────────────────────────────────────┘
```

**Request flows**

- **Create** — `POST /urls` validates the URL, generates a random base62 code
  (length 7), and writes the item with an `attribute_not_exists(PK)` condition.
  On the rare code collision it retries (up to 5 times) with a fresh code.
- **Redirect** — `GET /{code}` looks up the item, checks the optional `expiresAt`
  TTL, increments `clickCount`, and returns a **302** (never 301) so browsers do
  not cache the redirect and every click is counted. Click-counting failures
  never block the redirect.

**Data model (single-table)**

| Attribute              | Example                  | Purpose                         |
| ---------------------- | ------------------------ | ------------------------------- |
| `PK`                   | `SHORT#aB3x9Qz`          | Partition key                   |
| `SK`                   | `META`                   | Sort key                        |
| `longUrl`              | `https://example.com`    | Destination                     |
| `ownerId`              | `anonymous`              | Link owner                      |
| `createdAt`            | `2026-06-14T07:00:00Z`   | Creation timestamp (UTC)        |
| `clickCount`           | `0`                      | Incremented on each redirect    |
| `GSI1PK` / `GSI1SK`    | `OWNER#anonymous` / time | GSI1 — list all links by owner  |
| `expiresAt` (optional) | epoch seconds            | DynamoDB TTL auto-deletion      |

**Security & cost posture**

- Least-privilege IAM: the create function gets only `PutItem`; the redirect
  function gets only `GetItem` + `UpdateItem`, each scoped to the one table.
- DynamoDB and API Gateway are pay-per-request; the stage is throttled
  (burst 20, rate 10 req/s).
- CloudWatch log groups have a 14-day retention.

---

## Repository Layout

```
serverless-url-shortner/
├── app/                       # all Python
│   ├── src/
│   │   ├── create/handler.py    # POST /urls  — create short link
│   │   └── redirect/handler.py  # GET  /{code} — redirect + count
│   ├── tests/                   # pytest suites (moto-mocked)
│   └── requirements-dev.txt
├── terraform/
│   ├── bootstrap/             # one-time: S3 state bucket + lock table
│   ├── infra/                 # the project (remote state in S3)
│   │   └── modules/           # reusable modules: dynamodb, lambda
└── other/                     # manual AWS-CLI checks & deliverables
```

---

## Prerequisites

- An **AWS account** and credentials configured locally
  (`aws configure` or environment variables).
- **Terraform** `>= 1.5`
- **Python** `3.13` (the Lambda runtime target)
- **AWS CLI** v2 (for the optional manual check scripts)
- Permissions to create Lambda, API Gateway, DynamoDB, S3, IAM, and CloudWatch
  resources in `ap-south-1`.

---

## Installation & Setup

### 1. Clone

```bash
git clone <your-repo-url>
cd serverless-url-shortner
```

### 2. Python environment & tests

> **Always get `pytest` green before deploying.**

```bash
cd app
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

### 3. Bootstrap remote state (one time per account)

Creates the versioned/encrypted S3 bucket and the DynamoDB lock table that the
main project's remote state depends on.

```bash
cd terraform/bootstrap
terraform init
terraform apply
```

> The bucket name in `terraform/bootstrap/terraform.tfvars` and
> `terraform/infra/backend.tf` must match and be **globally unique** — change
> both if `shortify-url-shortener-tf-state` is already taken.

### 4. Provision the application infrastructure

```bash
cd ../infra
terraform init     # connects to the S3 backend created above
terraform plan
terraform apply
```

Terraform zips each Lambda's source folder, creates the DynamoDB table, wires up
the HTTP API routes, and prints the API base URL.

---

## Environment & Configuration

### Terraform variables (`terraform/infra/terraform.tfvars`)

| Variable            | Default / Example                    | Description                              |
| ------------------- | ------------------------------------ | ---------------------------------------- |
| `aws_region`        | `ap-south-1`                         | Region for all resources                 |
| `state_bucket_name` | `shortify-url-shortener-tf-state`    | S3 bucket for remote state (must be unique) |
| `lock_table_name`   | `shortify-url-shortener-tf-lock`     | DynamoDB table for state locking         |
| `project_name`      | `shortify`                           | Resource name prefix                     |

### Lambda environment variables (set by Terraform)

| Variable     | Value           | Used by             |
| ------------ | --------------- | ------------------- |
| `TABLE_NAME` | `shortify-urls` | both Lambda handlers |

### Tunable Lambda module defaults

`runtime python3.13` · `handler handler.lambda_handler` · `timeout 10s` ·
`memory 128 MB` · `log retention 14 days` · `enable_tracing false` (X-Ray).

---

## Usage

After `terraform apply`, grab the base URL:

```bash
cd terraform/infra
API_URL=$(terraform output -raw api_base_url)
```

### Create a short link

```bash
curl -s -X POST "$API_URL/urls" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/some/long/path"}'
```

```json
{
  "shortCode": "aB3x9Qz",
  "longUrl": "https://example.com/some/long/path",
  "createdAt": "2026-06-14T07:00:00Z"
}
```

### Follow the short link

```bash
curl -i "$API_URL/aB3x9Qz"
# HTTP/1.1 302 Found
# Location: https://example.com/some/long/path
```

Or just open `$API_URL/aB3x9Qz` in a browser.

---

## API Documentation

Base URL: the API Gateway stage `invoke_url` (Terraform output `api_base_url`).

### `POST /urls` — create a short link

**Request body** (JSON)

| Field     | Type   | Required | Notes                                              |
| --------- | ------ | -------- | -------------------------------------------------- |
| `url`     | string | yes      | Must be `http://` or `https://`, ≤ 2048 characters |
| `ownerId` | string | no       | Defaults to `anonymous`                            |

**Responses**

| Status | Body                                                       | Meaning                          |
| ------ | ---------------------------------------------------------- | -------------------------------- |
| `201`  | `{ "shortCode", "longUrl", "createdAt" }`                  | Created                          |
| `400`  | `{ "error": "Body must be valid JSON." }`                  | Body was not valid JSON          |
| `400`  | `{ "error": "Field 'url' must be a valid http or https link." }` | Missing/invalid URL       |
| `500`  | `{ "error": "Could not save the link." }`                 | DynamoDB write failed            |
| `500`  | `{ "error": "Could not generate a unique code, please retry." }` | Exhausted collision retries |

**Example**

```bash
curl -X POST "$API_URL/urls" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://anthropic.com", "ownerId": "kaveen"}'
```

### `GET /{code}` — redirect to the original URL

**Path parameter**

| Name   | Description                       |
| ------ | --------------------------------- |
| `code` | The short code returned at create |

**Responses**

| Status | Headers / Body                                        | Meaning                                    |
| ------ | ----------------------------------------------------- | ------------------------------------------ |
| `302`  | `Location: <longUrl>`, `Cache-Control: no-store …`    | Redirect; `clickCount` incremented         |
| `404`  | `Short link not found.`                               | Unknown, missing, or expired (TTL) code    |
| `500`  | `Lookup failed.`                                       | DynamoDB read failed                       |

> The redirect deliberately returns **302** with no-store caching so every click
> reaches the function and the count stays accurate.

---

## Testing

```bash
cd app
source .venv/bin/activate
pytest
```

Tests use **moto** to mock DynamoDB, so they run fully offline with no AWS
credentials or real resources.

---

## Teardown

```bash
cd terraform/infra
terraform destroy

# Optional: remove the remote-state backend too (do this last)
cd ../bootstrap
terraform destroy
```

---

## Roadmap

- [ ] QR-code generation for short links
- [ ] List-by-owner endpoint (GSI1 is already in place)
- [ ] Custom / vanity short codes
- [ ] Per-owner authentication

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE)
file for details.
