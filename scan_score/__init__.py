# Windows-friendly MySQL backend fallback.
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except Exception:
    pass
