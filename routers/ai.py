import logging 
from typing import Annotated, List

from fastapi import APIRouter, Depends,HTTPException
from pydantic import BaseModel
from starlette import status

from routers.auth import db_dependency,get_current_user
from app.models import Product , cartItem
from routers.ai_service import AIServiceError,generate_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai",tags=["AI Assistant"])

user_dependency = Annotated[dict,Depends(get_current_user)]

SYSTEM_PROMPT = (
    "You are a shopping assistant for an online store. Use ONLY the product data "
    "provided. Never invent specifications, brands or prices. If the data is too "
    "thin to justify the price, say so plainly. Candidates are NOT guaranteed to be "
    "the same kind of product: suggest a candidate only if a buyer could realistically "
    "use it as a substitute, otherwise return an empty alternatives list. "
    "Reply with JSON only, in this shape: "
    '{"explanation": str, "key_features": [str], '
    '"alternatives": [{"product_id": int, "why_cheaper": str, "tradeoffs": str}]}. '
    "Only use product_id values from the candidates list."
)
class AlternativeOut(BaseModel):
    product_id : int
    name : str
    price : float
    why_cheaper : str
    tradeoffs : str

class PriceExplainationOut(BaseModel):
    product_id :int
    name:str
    price : float
    explaination:str
    key_features:List[str]
    alternatives : List[AlternativeOut]


def _product_dict(p:Product) -> dict:
    return {
        "product_id" : p.id,
        "name" : p.name,
        "description" : p.description,
        "price" : float(p.price),
    }

@router.post("/cart/{item_id}/explain-price",response_model=PriceExplainationOut)
def explain_price(item_id:int,db:db_dependency,current_user:user_dependency):
    ''' # Admin tokens carry an id from the admins table, which can collide with a
    # users.id, so cart access is limited to the 'user' role.'''
    if current_user.get("role") != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,deatil = "User only")

    item = (
        db.query(cartItem)
        .filter(cartItem.id == item_id,cartItem.user_id == current_user["id"])
        .first()
    )
    if not item:
        raise HTTPException(status_code=404,detail="Cart Item not found")

    product = item.product
    if not product:
        raise HTTPException(status_code=404,detail = "Product not found")

    candidates = (
        db.query(Product)
        .filter(
            Product.id != product.id,
            Product.quantity > 0,
            Product.price < product.price,
            Product.price >= product.price * 0.3,
        )
        .order_by(Product.price.desc())
        .limit(10)
        .all()
    )
    candidate_map = {c.d : c for c in candidates}

    user_prompt = (
           f"Product in cart: {_product_dict(product)}\n"
        f"Cheaper candidates (may be empty): {[_product_dict(c) for c in candidates]}\n"
        "Explain why the cart product is priced as it is and what the buyer gets. "
        "For each candidate worth suggesting, say why it costs less and what the buyer gives up."
    )
    try:
        ai = generate_json(SYSTEM_PROMPT, user_prompt)
    except AIServiceError:
        logger.exception("AI call failed for cart item %s", item_id)
        raise HTTPException(status_code=503, detail="AI assistant is temporarily unavailable")
 
    # Hallucination guard: keep only IDs from the candidate set, rebuild name/price from the DB.
    alternatives, seen, dropped = [], set(), 0
    for alt in ai.get("alternatives", []):
        pid = alt.get("product_id")
        if pid in candidate_map and pid not in seen:
            seen.add(pid)
            c = candidate_map[pid]
            alternatives.append(
                AlternativeOut(
                    product_id=c.id,
                    name=c.name,
                    price=float(c.price),
                    why_cheaper=str(alt.get("why_cheaper", "")),
                    tradeoffs=str(alt.get("tradeoffs", "")),
                )
            )
        else:
            dropped += 1
    if dropped:
        logger.warning("Dropped %d hallucinated/duplicate alternative(s)", dropped)
 
    return PriceExplainationOut(
        product_id=product.id,
        name=product.name,
        price=float(product.price),
        explanation=str(ai.get("explanation", "")),
        key_features=[str(f) for f in ai.get("key_features", [])],
        alternatives=alternatives,  # empty list = cold-start fallback
    )
 