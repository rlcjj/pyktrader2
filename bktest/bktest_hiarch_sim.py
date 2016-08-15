import misc
import data_handler as dh
import pandas as pd
import json
import numpy as np
import strategy as strat
import datetime
import backtest
import sys

def hiarch_sim( mdf, config):
    tcost = config['trans_cost']
    unit = config['unit']
    offset = config['offset']
    pos_class = config['pos_class']
    pos_args  = config['pos_args']    
    freq = config['freq']
    param = config['param']
    signal_func = config['signal_func']
    signal_args = config['signal_args']
    signal_level = config['signal_level']
    close_daily = config['close_daily']
    for idx, (f, sfunc, sargs, slvl)  in enumerate(zip(freq, signal_func, signal_args, signal_level)):
        df = dh.conv_ohlc_freq(mdf, f, extra_cols=['contract'])
        if idx == 0:
            xdf = df
        signal = eval(sfunc)(df, **sargs)
        long_lvl  = slvl[0] + slvl[1]
        short_lvl = slvl[0] - slvl[1]
        long_ind = (signal > long_lvl)
        short_ind = (signal < short_lvl)
        xdata = pd.concat([signal, long_ind, short_ind], axis = 1, keys = ['signal'+str(idx), 'long_ind'+str(idx), 'short_ind'+str(idx)]).shift(1)
        xdf = xdf.join(xdata, how = 'left').fillna(method='ffill')
    xdf['close_ind'] = np.isnan(xdf['close'].shift(-1))
    if close_daily:
        daily_end = (xdf['date']!=xdf['date'].shift(-1))
        xdf['close_ind'] = xdf['close_ind'] | daily_end        
    xdf['pos'] = 0
    xdf['cost'] = 0
    xdf['traded_price'] = xdf.open
    curr_pos = []
    closed_trades = []
    tradeid = 0
    for idx, dd in enumerate(xdf.index):
        mslice = xdf.ix[dd]
        min_id = mslice.min_id
        if len(curr_pos) == 0:
            pos = 0
        else:
            pos = curr_pos[0].pos
        xdf.set_value(dd, 'pos', pos)
        if mslice.close_ind:
            if pos!=0:
                curr_pos[0].close(mslice.open - misc.sign(pos) * offset, dd)
                tradeid += 1
                curr_pos[0].exit_tradeid = tradeid
                closed_trades.append(curr_pos[0])
                curr_pos = []
                xdf.set_value(dd, 'cost', xdf.at[dd, 'cost'] - abs(pos) * ( mslice.open * tcost))
                xdf.set_value(dd, 'traded_price', mslice.open - misc.sign(pos) * offset)
                pos = 0
        else:
            if (pos !=0):
                direction = 0
                long_ind = True in [mslice.getattr('long_ind'+str(idx) for idx in range(len(freq))]
                short_ind = True in [mslice.getattr('short_ind'+str(idx) for idx in range(len(freq))]
                if ((pos < 0) and long_ind) or ((pos > 0) and short_ind):
                    curr_pos[0].close(mslice.open - misc.sign(pos) * offset, dd)
                    tradeid += 1
                    curr_pos[0].exit_tradeid = tradeid
                    closed_trades.append(curr_pos[0])
                    curr_pos = []
                    xdf.set_value(dd, 'cost', xdf.at[dd, 'cost'] - abs(pos) * (mslice.open * tcost))
                    xdf.set_value(dd, 'traded_price', mslice.open - misc.sign(pos) * offset)
                    pos = 0                
            long_ind = False not in [mslice.getattr('long_ind'+str(idx) for idx in range(len(freq))]
            short_ind = False not in [mslice.getattr('short_ind'+str(idx) for idx in range(len(freq))]            
            if (long_ind or short_ind) and (pos == 0):
                target_pos = long_ind * unit - short_ind * unit
                new_pos = pos_class([mslice.contract], [1], target_pos, mslice.open, mslice.open, **pos_args)
                tradeid += 1
                new_pos.entry_tradeid = tradeid
                new_pos.open(mslice.open + misc.sign(target_pos)*offset, dd)
                curr_pos.append(new_pos)
                pos = target_pos
                xdf.set_value(dd, 'cost', xdf.at[dd, 'cost'] -  abs(target_pos) * (mslice.open * tcost))
                xdf.set_value(dd, 'traded_price', mslice.open + misc.sign(target_pos)*offset)            
        xdf.set_value(dd, 'pos', pos)
    return (xdf, closed_trades)

def gen_config_file(filename):
    sim_config = {}
    sim_config['sim_func']  = 'bktest_hiarch_sim.hiarch_sim'
    sim_config['scen_keys'] = ['freq', 'signal_args']
    sim_config['sim_name']   = 'chanbreak_'
    sim_config['products']   = ['rb', 'i', 'j', 'jm', 'ZC', 'ru', 'ni', 'y', 'p', 'm', 'RM', 'cs', 'jd', 'a', 'l', 'pp', 'TA', 'MA', 'bu', 'cu', 'al', 'ag', 'au']
    sim_config['start_date'] = '20150102'
    sim_config['end_date']   = '20160708'
    sim_config['need_daily'] = False
    sim_config['signal_args'] = [[{'n_fast': 13, 'n_slow': 5, 'n_signal': 5 }, {'n_fast': 13, 'n_slow': 5, 'n_signal': 5 }], \
                        [{'n_fast': 13, 'n_slow': 7, 'n_signal': 7}, {'n_fast': 13, 'n_slow': 7, 'n_signal': 7}], \
                        [{'n_fast': 20, 'n_slow': 7, 'n_signal': 7}, {'n_fast': 20, 'n_slow': 7, 'n_signal': 7}]]
    sim_config['freq'] = [['15min', '60min'], ['15min', '90min'], ['5min', '30min'], ['5min', '60min']]
    sim_config['pos_class'] = 'strat.TradePos'
    #sim_config['pos_class'] = 'strat.ParSARTradePos'
    #sim_config['pos_args'] = [{'reset_margin': 1, 'af': 0.02, 'incr': 0.02, 'cap': 0.2},\
    #                            {'reset_margin': 2, 'af': 0.02, 'incr': 0.02, 'cap': 0.2},\
    #                            {'reset_margin': 3, 'af': 0.02, 'incr': 0.02, 'cap': 0.2},\
    #                            {'reset_margin': 1, 'af': 0.01, 'incr': 0.01, 'cap': 0.2},\
    #                            {'reset_margin': 2, 'af': 0.01, 'incr': 0.01, 'cap': 0.2},\
    #                            {'reset_margin': 3, 'af': 0.01, 'incr': 0.01, 'cap': 0.2}]
    sim_config['offset']    = 1
    config = {'capital': 10000,
              'trans_cost': 0.0,
              'unit': 1,
              'stoploss': 0.0,
              'close_daily': False,
              'pos_update': False,
              'signal_func': ['dh.MACD', 'dh.MACD'],
              'signal_level': [[0, 0], [0, 0]],
              'exit_min': 2055,
              'pos_args': {},
              }
    sim_config['config'] = config
    with open(filename, 'w') as outfile:
        json.dump(sim_config, outfile)
    return sim_config
    
if __name__=="__main__":
    args = sys.argv[1:]
    if len(args) < 1:
        print "need to input a file name for config file"
    else:
        gen_config_file(args[0])
    pass
