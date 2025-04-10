export interface Order {
    order_id: string;
    type?: string;
    size?: number;
    price?: number;
    time: string;
    reason?: string;
    remaining_size?: number;
    trade_id?: string;
    anomaly_score?: number;
    spoofing_threshold?: number;
}
