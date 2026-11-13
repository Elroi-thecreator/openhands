
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/calculate', methods=['POST'])
def calculate_api():
    data = request.json or {}
    units = float(data.get('units', 0))
    tariff = data.get('tariff', 'domestic')
    cycle = data.get('cycle', 'bimonthly')
    include_subsidy = bool(data.get('subsidy', True))

    scale = 1.0 if cycle == 'bimonthly' else 0.5
    slabs = []
    fixed_charges = 0.0
    subsidy_savings = 0.0

    if tariff in ['hut', 'agriculture']:
        slabs.append({'range': 'All Units', 'units': units, 'rate': 0.0, 'cost': 0.0})
    elif tariff == 'commercial':
        mult = 2 if cycle == 'bimonthly' else 1
        limit1 = 100 * mult
        if units <= limit1:
            slabs.append({'range': f'0 - {limit1}', 'units': units, 'rate': 6.30, 'cost': units * 6.30})
        else:
            slabs.append({'range': f'0 - {limit1}', 'units': limit1, 'rate': 6.30, 'cost': limit1 * 6.30})
            rem = units - limit1
            slabs.append({'range': f'>{limit1}', 'units': rem, 'rate': 9.95, 'cost': rem * 9.95})
        fixed_charges = 100.0 * mult
    elif tariff == 'powerloom':
        mult = 2 if cycle == 'bimonthly' else 1
        limit1 = 500 * mult
        limit2 = 1000 * mult
        if units <= limit1:
            slabs.append({'range': f'0 - {limit1}', 'units': units, 'rate': 0.0, 'cost': 0.0})
        elif units <= limit2:
            slabs.append({'range': f'0 - {limit1}', 'units': limit1, 'rate': 0.0, 'cost': 0.0})
            rem = units - limit1
            slabs.append({'range': f'{limit1+1} - {limit2}', 'units': rem, 'rate': 3.65, 'cost': rem * 3.65})
        else:
            slabs.append({'range': f'0 - {limit1}', 'units': limit1, 'rate': 0.0, 'cost': 0.0})
            slabs.append({'range': f'{limit1+1} - {limit2}', 'units': 500 * mult, 'rate': 3.65, 'cost': 500 * mult * 3.65})
            rem = units - limit2
            slabs.append({'range': f'>{limit2}', 'units': rem, 'rate': 6.35, 'cost': rem * 6.35})
    else:
        # Domestic 1A
        s100 = 100 * scale
        s200 = 200 * scale
        s400 = 400 * scale
        s500 = 500 * scale

        if units <= s500:
            u100 = min(units, s100)
            r100 = 0.0 if include_subsidy else 4.70
            c100 = u100 * r100
            slabs.append({'range': f'0 - {int(s100)}', 'units': u100, 'rate': r100, 'cost': c100})
            if include_subsidy:
                subsidy_savings = u100 * 4.70

            if units > s100:
                u200 = min(units - s100, 100 * scale)
                slabs.append({'range': f'{int(s100+1)} - {int(s200)}', 'units': u200, 'rate': 2.35, 'cost': u200 * 2.35})
                if units > s200:
                    u400 = min(units - s200, 200 * scale)
                    slabs.append({'range': f'{int(s200+1)} - {int(s400)}', 'units': u400, 'rate': 4.70, 'cost': u400 * 4.70})
                    if units > s400:
                        u500 = units - s400
                        slabs.append({'range': f'{int(s400+1)} - {int(s500)}', 'units': u500, 'rate': 6.30, 'cost': u500 * 6.30})
        else:
            u100 = s100
            r100 = 0.0 if include_subsidy else 4.70
            slabs.append({'range': f'0 - {int(s100)}', 'units': u100, 'rate': r100, 'cost': u100 * r100})
            if include_subsidy:
                subsidy_savings = u100 * 4.70

            u400 = 300 * scale
            slabs.append({'range': f'{int(s100+1)} - {int(s400)}', 'units': u400, 'rate': 4.70, 'cost': u400 * 4.70})

            u500 = 100 * scale
            slabs.append({'range': f'{int(s400+1)} - {int(s500)}', 'units': u500, 'rate': 6.30, 'cost': u500 * 6.30})

            rem = units - s500
            u600 = min(rem, 100 * scale)
            slabs.append({'range': f'{int(s500+1)} - {int(600*scale)}', 'units': u600, 'rate': 8.40, 'cost': u600 * 8.40})
            rem -= u600

            if rem > 0:
                u800 = min(rem, 200 * scale)
                slabs.append({'range': f'{int(600*scale+1)} - {int(800*scale)}', 'units': u800, 'rate': 9.50, 'cost': u800 * 9.50})
                rem -= u800

                if rem > 0:
                    u1000 = min(rem, 200 * scale)
                    slabs.append({'range': f'{int(800*scale+1)} - {int(1000*scale)}', 'units': u1000, 'rate': 10.50, 'cost': u1000 * 10.50})
                    rem -= u1000

                    if rem > 0:
                        slabs.append({'range': f'>{int(1000*scale)}', 'units': rem, 'rate': 11.55, 'cost': rem * 11.55})

    energy_total = sum(s['cost'] for s in slabs)
    total_amount = energy_total + fixed_charges

    return jsonify({
        'total': total_amount,
        'energy_total': energy_total,
        'fixed_charges': fixed_charges,
        'subsidy_savings': subsidy_savings,
        'slabs': slabs
    })

if __name__ == '__main__':
    # Running on 0.0.0.0 and port 54278 as specified in runtime parameters
    app.run(host='0.0.0.0', port=54278, debug=False)

