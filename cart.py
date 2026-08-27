# start implementing Cart feature
from typing import Annotated,List
from fastapi import APIRouter , Depends, HTTPException, status
from auth import get_current_user,db_dependency
from models import cartItem,Product,CartItemCreate,CartItemUpdate,CartItemSchema

router = APIRouter(
    prefix='/cart',
    tags = ['cart']
)

user_dependency = Annotated[dict,Depends(get_current_user)]

@router.post("/add",response_model=CartItemSchema, status_code=status.HTTP_201_CREATED)
def add_to_cart(item:CartItemCreate, user: user_dependency, db:db_dependency):
    product = db.query(Product).filter(Product.id == item.product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Product not found!!")

    existing_item = db.query(cartItem).filter(
        cartItem.user_id == user['id'],
        cartItem.product_id == item.product_id
    ).first()


    requested_total = item.quantity + (existing_item.quantity if existing_item else 0)
    if requested_total > product.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail = f"Only {product.quantity} units of {product.name} are available..."
        )
    if existing_item:
        existing_item.quantity = requested_total
        db.commit()
        db.refresh(existing_item)
        return existing_item

    new_item = cartItem(user_id=user['id'],product_id = item.product_id, quantity = item.quantity)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

@router.get("/",response_model=List[CartItemSchema])
def get_cart(user: user_dependency, db: db_dependency):
    return db.query(cartItem).filter(cartItem.user_id == user['id']).all()

@router.put("/{item_id}", response_model=CartItemSchema)
def update_cart_item(item_id: int,update:CartItemUpdate, user:user_dependency,db : db_dependency):
    cart_item = db.query(cartItem).filter(
        cartItem.id == item_id,
        cartItem.user_id == user['id']
    ).first()

    if not cart_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail = "cart item not found..")

    if update.quantity > cart_item.product.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {cart_item.product.quantity} units of {cart_item.product.name} are available"
        )

    cart_item.quantity = update.quantity
    db.commit()
    db.refresh(cart_item)
    return cart_item

@router.delete("/{item_id}")
def remove_cart_item(item_id:int, user: user_dependency,db:db_dependency):
    cart_item = db.query(cartItem).filter(
        cartItem.id == item_id,
        cartItem.user_id == user['id']
    ).first()
    if not cart_item: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail= "Item is not found in cart")

    db.delete(cart_item)
    db.commit()
    return {"message" : "Item removed from cart"}
@router.delete("/")
def clear_cart(user: user_dependency, db:db_dependency):
    db.query(cartItem).filter(cartItem.user_id == user['id']).delete()
    db.commit()
    return {"message":"cart cleared"}