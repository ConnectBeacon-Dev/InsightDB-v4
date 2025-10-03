# Quick Command Reference

## Build Views
```bash
python etl/build_views_pandas.py --inputs inputs --views views
```

## Build Index
```bash
python engine/full_engine_query.py index --views views --force
```

## Queries

### Industry + Location
```bash
python engine/full_engine_query.py query --views views --ask "electrical companies in pune" --top-k 5
```

### Company-Specific
```bash
python engine/full_engine_query.py query --views views --ask "Pan of K G DENIM Limited" --top-k 1
python engine/full_engine_query.py query --views views --ask "Contact details of MADHYA BHARAT AGRO PRODUCTS LIMITED" --top-k 1
python engine/full_engine_query.py query --views views --ask "Address of GMO GLOBALSIGN CERTIFICATE SERVICES" --top-k 1
```

### Filter Queries
```bash
python engine/full_engine_query.py query --views views --ask "List of MSME in India" --top-k 15
python engine/full_engine_query.py query --views views --ask "list defence companies" --top-k 10
python engine/full_engine_query.py query --views views --ask "companies in pune" --top-k 10
```

### Generic Queries
```bash
python engine/full_engine_query.py query --views views --ask "companies doing research in advanced materials" --top-k 10
