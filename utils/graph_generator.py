"""Генератор графиков изменения цен."""
import io
from datetime import datetime
from typing import List
import matplotlib
matplotlib.use('Agg')  # Без GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from services.db import PriceHistoryRow

# Настройка для корректного отображения русского текста
plt.rcParams['font.family'] = 'DejaVu Sans'


async def generate_price_graph(
    history: List[PriceHistoryRow],
    product_name: str,
    discount: int = 0
) -> io.BytesIO:
    """
    Генерирует график изменения цен.
    
    Args:
        history: История цен (от новых к старым)
        product_name: Название товара
        
    Returns:
        BytesIO объект с PNG изображением
    """
    if not history:
        raise ValueError("История пуста")
    
    # Разворачиваем историю (от старых к новым)
    history = list(reversed(history))

    # Извлекаем данные
    dates = [h.recorded_at for h in history]

    # Применяем скидку если есть
    if discount > 0:
        from utils.wb_utils import apply_wallet_discount
        prices = [apply_wallet_discount(h.product_price, discount) for h in history]
    else:
        prices = [h.product_price for h in history]
        
        # Создаем график
        fig, ax = plt.subplots(figsize=(12, 6))
    
    # Рисуем линию цены
    ax.plot(dates, prices, marker='o', linewidth=2, markersize=4, color='#2196F3')
    
    # Заливка под графиком
    ax.fill_between(dates, prices, alpha=0.3, color='#2196F3')
    
    # Настройка осей
    ax.set_xlabel('Дата', fontsize=11)
    ylabel = f'Цена с WB кошельком ({discount}%), ₽' if discount > 0 else 'Цена, ₽'
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(f'График цен: {product_name[:50]}', fontsize=13, fontweight='bold')
    
    # Форматирование дат на оси X
    if len(dates) > 1:
        days_diff = (dates[-1] - dates[0]).days
        
        if days_diff <= 7:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
        elif days_diff <= 30:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%y'))
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    
    plt.xticks(rotation=45, ha='right')
    
    # Сетка
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Статистика
    min_price = min(prices)
    max_price = max(prices)
    current_price = prices[-1]
    
    stats_text = (
        f'Мин: {min_price}₽ | '
        f'Макс: {max_price}₽ | '
        f'Текущая: {current_price}₽'
    )
    
    ax.text(
        0.5, 0.98, stats_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment='top',
        horizontalalignment='center',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    )
    
    # Tight layout для красивого отображения
    plt.tight_layout()
    
    # Сохраняем в BytesIO
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return buf
