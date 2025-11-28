from dto import PriceHistoryDTO, ProductDTO, UserDTO
from entities import PriceHistory, Product, User
from enums import NotifyMode, Plan, SortMode


class UserMapper:

    @staticmethod
    def to_entity(dto: UserDTO) -> User:
        """DTO → Entity."""
        return User(
            id=dto.id,
            plan=Plan(dto.plan),                        # str → Enum
            discount_percent=dto.discount_percent,
            max_links=dto.max_links,
            dest=dto.dest,
            pvz_address=dto.pvz_address,
            sort_mode=SortMode(dto.sort_mode),          # str → Enum
            created_at=dto.created_at
        )

    @staticmethod
    def to_dto(entity: User) -> UserDTO:
        """Entity → DTO."""
        return UserDTO(
            id=entity.id,
            plan=entity.plan.value,                     # Enum → str
            discount_percent=entity.discount_percent,
            max_links=entity.max_links,
            dest=entity.dest,
            pvz_address=entity.pvz_address,
            sort_mode=entity.sort_mode.value,           # Enum → str
            created_at=entity.created_at
        )


class ProductMapper:

    @staticmethod
    def to_entity(dto: ProductDTO) -> Product:
        """DTO → Entity."""
        return Product(
            id=dto.id,
            user_id=dto.user_id,
            url=dto.url_product,
            nm_id=dto.nm_id,
            name=dto.name_product,
            custom_name=dto.custom_name,
            last_basic_price=dto.last_basic_price,
            last_product_price=dto.last_product_price,
            selected_size=dto.selected_size,
            notify_mode=(
                NotifyMode(dto.notify_mode)
                if dto.notify_mode is not None else NotifyMode.ANY
            ),
            notify_value=dto.notify_value,
            last_qty=dto.last_qty,
            out_of_stock=dto.out_of_stock,
            created_at=dto.created_at,
            updated_at=dto.updated_at
        )

    @staticmethod
    def to_dto(entity: Product) -> ProductDTO:
        """Entity → DTO."""
        return ProductDTO(
            id=entity.id,
            user_id=entity.user_id,
            url_product=entity.url,
            nm_id=entity.nm_id,
            name_product=entity.name,
            custom_name=entity.custom_name,
            last_basic_price=entity.last_basic_price,
            last_product_price=entity.last_product_price,
            selected_size=entity.selected_size,
            notify_mode=(
                entity.notify_mode.value
                if entity.notify_mode is not None else None
            ),
            notify_value=entity.notify_value,
            last_qty=entity.last_qty,
            out_of_stock=entity.out_of_stock,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )


class PriceHistoryMapper:
    @staticmethod
    def to_entity(dto: PriceHistoryDTO) -> PriceHistory:
        return PriceHistory(
            id=dto.id,
            product_id=dto.product_id,
            basic_price=dto.basic_price,
            product_price=dto.product_price,
            qty=dto.qty,
            recorded_at=dto.recorded_at
        )

    @staticmethod
    def to_dto(entity: PriceHistory) -> PriceHistoryDTO:
        return PriceHistoryDTO(
            id=entity.id,
            product_id=entity.product_id,
            basic_price=entity.basic_price,
            product_price=entity.product_price,
            qty=entity.qty,
            recorded_at=entity.recorded_at
        )
