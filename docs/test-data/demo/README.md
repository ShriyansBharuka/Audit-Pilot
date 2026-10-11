# Demo organisations: the client's files

The sales register and related-party list of each demo organisation (`docs/DEMO_ACCOUNTS.md`), as the client sent
them. Each comes as `.csv` and `.xlsx`, which parse to identical rows.

| Organisation | Sales register | Related-party list |
|---|---|---|
| Arnav Marine Systems Pvt Ltd | `arnav_sales_register.csv / .xlsx` | `arnav_related_parties.csv / .xlsx` |
| Medisync Pharma Distributors Pvt Ltd | `medisync_sales_register.csv / .xlsx` | `medisync_related_parties.csv / .xlsx` |
| Torqline Auto Components Ltd | `torqline_sales_register.csv / .xlsx` | `torqline_related_parties.csv / .xlsx` |

**How to upload one by hand:** sign in as that organisation's CFO (`cfo.<org>@example.com`) → **Upload data** →
Sales register / Related-party list. Accounts users can upload the register too. Upload a file only to its own
organisation: the register matches that organisation's books.

**What's planted (the auditor finds each one):**
- **Register:** one real invoice left out, one taxable value inflated by 10%, one invoice that isn't in the books,
  and the 2 April invoice listed as 31 March.
- **Related-party list:** the director's trading company is left off, so it is an undisclosed related party.

The exact invoice numbers are in `docs/DEMO_ACCOUNTS.md`. These files are already uploaded in the live demo, so
uploading one again gives the same findings. To show the difference, edit a value in the Excel file before
uploading it.
