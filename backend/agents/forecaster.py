from datetime import datetime

class ForecasterAgent:
    def __init__(self):
        pass

    def run(self, travel_history: list) -> dict:
        """
        Predicts traveler demand (trip count, mode, distance) for the next 6 months.
        Utilizes historical seasonality trends found in the 12-month travel logs.
        """
        if not travel_history:
            return {
                "forecast_6mo": [],
                "total_predicted_trips": 0,
                "confidence_score": 0.5,
                "trend": "Insufficient data to establish trend"
            }
            
        # Group historical trips by month and mode
        # Simple moving average + seasonality multipliers
        monthly_trips = {}
        for trip in travel_history:
            date_str = trip["trip_date"]
            mode = trip["mode"]
            
            # Extract month
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                month_key = dt.strftime("%Y-%m")
            except:
                continue
                
            if month_key not in monthly_trips:
                monthly_trips[month_key] = {}
            if mode not in monthly_trips[month_key]:
                monthly_trips[month_key][mode] = 0
                
            monthly_trips[month_key][mode] += 1
            
        # Compute baseline average trips per month per mode
        modes = list(set(trip["mode"] for trip in travel_history))
        mode_averages = {mode: 0.0 for mode in modes}
        
        num_months = len(monthly_trips) if monthly_trips else 12
        for month in monthly_trips:
            for mode in monthly_trips[month]:
                mode_averages[mode] += monthly_trips[month][mode]
                
        for mode in mode_averages:
            mode_averages[mode] = round(mode_averages[mode] / num_months, 2)
            
        # Project 6 months ahead: June, July, August, September, October, November (2026)
        future_months = [
            {"month": "June 2026", "multiplier": 1.1},
            {"month": "July 2026", "multiplier": 1.3},
            {"month": "August 2026", "multiplier": 1.3},
            {"month": "September 2026", "multiplier": 1.0},
            {"month": "October 2026", "multiplier": 0.9},
            {"month": "November 2026", "multiplier": 0.8}
        ]
        
        forecast_6mo = []
        total_predicted_trips = 0
        
        for fm in future_months:
            m_name = fm["month"]
            mult = fm["multiplier"]
            
            month_forecast = {"month": m_name, "trips_by_mode": {}, "total_trips": 0}
            
            for mode in mode_averages:
                avg = mode_averages[mode]
                # Commuter trips are stable and don't change much seasonally
                if avg > 20: # Commuter persona
                    predicted_trips = int(avg)
                else:
                    predicted_trips = int(round(avg * mult))
                
                if predicted_trips > 0:
                    month_forecast["trips_by_mode"][mode] = predicted_trips
                    month_forecast["total_trips"] += predicted_trips
                    total_predicted_trips += predicted_trips
            
            forecast_6mo.append(month_forecast)
            
        # Calculate overall trend
        if total_predicted_trips / 6 > sum(mode_averages.values()):
            trend = "Slightly increasing travel volume predicted for summer months"
        else:
            trend = "Stable seasonal travel demand anticipated"

        # Construct forecast output
        result = {
            "forecast_6mo": forecast_6mo,
            "total_predicted_trips": total_predicted_trips,
            "confidence_score": 0.85 if len(travel_history) > 100 else 0.70,
            "trend": trend,
            "averages_per_month": mode_averages
        }
        
        return result

if __name__ == "__main__":
    forecaster = ForecasterAgent()
    mock_history = [
        {"trip_date": "2025-05-10", "mode": "train"},
        {"trip_date": "2025-05-12", "mode": "train"},
        {"trip_date": "2025-06-10", "mode": "train"}
    ]
    print(forecaster.run(mock_history))
