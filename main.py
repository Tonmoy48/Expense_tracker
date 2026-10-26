from fastapi import FastAPI
import models
from database import engine
from router import auth
from router import transactions

app = FastAPI()
app.include_router(transactions.router)

models.Base.metadata.create_all(bind=engine)
app.include_router(auth.router)

@app.get("/")
def root():
    return {"message": "Expense Tracker API is running"}