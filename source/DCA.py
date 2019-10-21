"""
add new features for DCA detection
~~~~~~~~~~~~~~~~~~~~~


"""
import statistics
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from itertools import groupby
from ventmap.breath_meta import get_experimental_breath_meta, get_production_breath_meta


def repeatingNumbers(numList):
    i = 0
    df = pd.DataFrame()
    while i < len(numList) - 1:
        n = numList[i]
        startIndex = i
        while i < len(numList) - 1 and numList[i] == numList[i + 1]:
            i = i + 1

        endIndex = i
        
        df = df.append({'T_F': n, 'startIndex': startIndex, 'endIndex': endIndex, "length":endIndex-startIndex+1}, ignore_index=True)

        i = i + 1
    return df


def find_flat_df(breath):
    
    # FIND THE INTERVAL OF ZERO PHASE, WILL BE NEEDED TO calculate slope
    br_id = breath["rel_bn"]
    #print(br_id)
    dt = breath["dt"]
    flow = breath["flow"]
    pressure = breath["pressure"]
    rel_time_array = [i * dt for i in range(len(flow))]
    df_t_flow_pres = pd.DataFrame({'t':rel_time_array,'flow':flow,'pressure':pressure})

    df_t_flow_pres_0 = df_t_flow_pres[df_t_flow_pres.flow.idxmax():]
    maxid = df_t_flow_pres.flow.idxmax()
    minid = df_t_flow_pres_0.flow.idxmin()
    df_t_flow_pres_0 = df_t_flow_pres_0.loc[maxid:minid]
    
    slopes= np.diff(df_t_flow_pres_0.flow)


    flow_5 = abs(df_t_flow_pres_0.flow)<0.5
    slope_3 = pd.Series(abs(np.array(slopes)))<0.3
    slope_3=slope_3.append(pd.Series([False]), ignore_index=True)
    slope_3.index=flow_5.index
    df_f_s = pd.DataFrame({'flow' : flow_5,'slope' : slope_3})
    df_f_s["sat_2"] = df_f_s.flow.astype(int) + df_f_s.slope.astype(int) ==2

    df_f_s["row_num"] = range(df_f_s.shape[0])
    df_f_s["breath_id"] = df_f_s.index
    
    df_repeat = repeatingNumbers(df_f_s["sat_2"].tolist())
    df_repeat_1=df_repeat[df_repeat.T_F==1]
    if df_repeat_1.empty:
        flat = pd.DataFrame()
    else:
        df_repeat_1_max=df_repeat_1.loc[df_repeat_1.length.idxmax()]

        startid = df_repeat_1_max.startIndex
        endid = df_repeat_1_max.endIndex

        start_br_id = df_f_s.breath_id[df_f_s.row_num==startid]
        end_br_id = df_f_s.breath_id[df_f_s.row_num==endid]


        flat=df_t_flow_pres.loc[int(start_br_id):(int(end_br_id)+1)]

    return flat




def find_flat_num(breath):
    # RETURN the number of data points around 0
    #threshold : abs(flow) <0.5 ; abs(diff(neighbor ))<0.3
    flow = breath['flow']
    dt = breath['dt']
    flow_0 = flow[flow.index(max(flow)):(len(flow)+1)]
    flow_0 = flow_0[1:(flow_0.index(min(flow_0))+1)]
    slopes=[np.diff(flow_0)]
    test=((abs(np.array(flow_0))<0.5).astype(int)[1:len(flow_0)] + (abs(np.array(slopes))<0.3).astype(int))==2
    L=test.astype(int)[0].tolist()
    # calculate consecutive nubmer of true of false
    grouped_L = [(k, sum(1 for i in g)) for k,g in groupby(L)]
    df=pd.DataFrame(grouped_L, columns=['T_F', 'num'])
    
    flat_num=max(df[df.T_F==1].num) if df[df.T_F==1].num.any() else 0
    return flat_num



def cal_slope_dyna(breath):
    # calculate slope for DCA_0.9 == 1
    meta = get_production_breath_meta(breath)
    meta_exp = get_experimental_breath_meta(breath)
    fbit = meta[6] 
    pbit = meta_exp[-1]
    f_pbit = fbit/pbit

    br_id = breath["rel_bn"]
   
    dt = breath["dt"]
    
    flow = breath["flow"]
    pressure = breath["pressure"]
    rel_time_array = [i * dt for i in range(len(flow))]
    df_t_flow_pres = pd.DataFrame({'t':rel_time_array,'flow':flow,'pressure':pressure})
    
    if f_pbit <= 0.9 :
        
        #fbit=DCA_detect[DCA_detect.breath_id==br_id].fbit.values[0]
        #pbit=DCA_detect[DCA_detect.breath_id==br_id].pbit.values[0]
        
        pressure_slope = df_t_flow_pres[df_t_flow_pres.t.between(fbit,pbit)]
        x = np.array([pressure_slope.t]).reshape((-1, 1))
        y = pressure_slope.pressure
        model = LinearRegression()
        model.fit(x, y)
        slope = model.coef_[0]

    else:
        slope = 0 
    return round(slope,2)

def cal_slope_static(breath):
    # calculate slope for flat_num >=7 (potential  static DCA)
    flat_num = find_flat_num(breath)
    br_id = breath["rel_bn"]
   
    dt = breath["dt"]
    
    flow = breath["flow"]
    pressure = breath["pressure"]
    rel_time_array = [i * dt for i in range(len(flow))]
    df_t_flow_pres = pd.DataFrame({'t':rel_time_array,'flow':flow,'pressure':pressure})
    
    if flat_num >=7 :
        target_slope=find_flat_df(breath)
        x = np.array([target_slope.t]).reshape((-1, 1))
        y = target_slope.pressure
        model = LinearRegression()
        model.fit(x, y)
        slope = model.coef_[0]
    else:
        slope = 0 
    return round(slope,2)


def median_flow_dyna(breath):
    # calculate slope for DCA_0.9 == 1
    meta = get_production_breath_meta(breath)
    meta_exp = get_experimental_breath_meta(breath)
    fbit = meta[6] 
    pbit = meta_exp[-1]
    f_pbit = fbit/pbit

    br_id = breath["rel_bn"]
   
    dt = breath["dt"]
    
    flow = breath["flow"]
    pressure = breath["pressure"]
    rel_time_array = [i * dt for i in range(len(flow))]
    df_t_flow_pres = pd.DataFrame({'t':rel_time_array,'flow':flow,'pressure':pressure})
    
    if f_pbit <= 0.9 :
        pressure_slope = df_t_flow_pres[df_t_flow_pres.t.between(fbit,pbit)]
        #x = np.array([pressure_slope.t]).reshape((-1, 1))
        y = pressure_slope.flow
        median_flow = statistics.median(y)


    else:
        median_flow = 0 
    return round(median_flow,2)