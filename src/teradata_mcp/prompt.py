PROMPTS = {
    "Analyze_database": """Please perform database analysis focusing on {database}.

    Include in your analysis:
    - List all tables in the database
    - List all objects in the database
    - Show detailed information about a database tables

    Format your analysis in a well-structured manner with clear headings and concise explanations.
    """,
    "Analyze_table": """Provide all the details about {table} in database {database}.

    Include in your analysis:
    1. Show detailed information about a table {table} in database {database}
    2. Check negative values in the table
    3. Check missing values in the table 
    4. Check distinct values in the table for each column
    4. Show mean and standard deviation for each numeric column in the table

    Be comprehensive but focus on quality over quantity."
    """,
    "glm": """Provide all the details about table {table} in database {database}.

    Include in your analysis:
   1. Train, predict and evaluate GLM regression model

   drop table train_test_out;

   create multiset table train_test_out as (
   select * from TD_TrainTestSplit (
      on {table} as InputTable
      USING
      IDColumn ('id')
      TrainSize (0.8)
      TestSize (0.2)
      Seed (17)
   ) as dt
   ) with data;

   2. Create train and test tables
   drop table weather_train;
   create multiset table weather_train as (
   select * from train_test_out where TD_IsTrainRow = 1
   ) with data;

   create multiset table weather_test as (
   select * from train_test_out where TD_IsTrainRow = 0
   ) with data;

   3. Scale the train and test data
   drop table fit_out_table;

   put all numeric columns from weather_train in the TargetColumns() function

   create multiset table fit_out_table as (
   select * from TD_ScaleFit (
      on weather_train as InputTable
      USING
      TargetColumns ()
      ScaleMethod ('STD')
   ) as dt
   ) with data;

   put all numeric columns from weather_train in the Accumulate() function

   drop table weather_train_scaled;

   create multiset table weather_train_scaled as (
   select * from TD_ScaleTransform (
      on weather_train as InputTable
      on fit_out_table as FitTable DIMENSION
      USING
      Accumulate()    
   ) as dt)
   with data;

   put all numeric columns from weather_test in the Accumulate() function

   drop table weather_test_scaled;

   create multiset table weather_test_scaled as (
   select * from TD_ScaleTransform (
      on weather_test as InputTable
      on fit_out_table as FitTable DIMENSION
      USING
      Accumulate('[1]','[3]','[9]','[11:12]','[23:25]')    
   ) as dt)
   with data;


   drop table fit_out_table;

   create multiset table fit_out_table as (
   select * from TD_OneHotEncodingFit (
      on weather_train_scaled as InputTable
      USING
      TargetColumn ('WindGustDir','WindDir9am','WindDir3pm','RainToday','RainTomorrow')
      IsInputDense('true')
      Approach('auto')
      CategoryCounts(16,16,16,2,2)
   ) as dt
   ) with data;

   put all numeric columns from weather_train in the TargetColumns() function

   drop table weather_train_s;

   create multiset table weather_train_s as (
   select * from TD_OneHotEncodingTransform (
      on weather_train_scaled as InputTable
      on fit_out_table as FitTable DIMENSION
      USING
      IsInputDense('true')    
   ) as dt)
   with data;

   create multiset table weather_test_s as (
   select * from TD_OneHotEncodingTransform (
      on weather_test_scaled as InputTable
      on fit_out_table as FitTable DIMENSION
      USING
      IsInputDense('true')    
   ) as dt)
   with data;

   4. Train a GLM model on train data. put all numbering columns from weather_train_s in the InputColumns() function

   drop table glm_model;

   create multiset table glm_model as (
   select * from TD_GLM (
      ON weather_train_s
         USING
         InputColumns('')
         ResponseColumn('rainfalltomorrow')
         Family('Gaussian')
   ) as dt
   ) with data;

   5. Predict test data using GLM model.

   drop table glm_predict_out;

   create multiset table glm_predict_out as (
   select * from TD_GLMPredict (
      ON weather_test_s as InputTable
      ON glm_model as ModelTable DIMENSION
      USING
      IDColumn('id')
      Accumulate('rainfalltomorrow')
   ) as dt
   ) with data;

   6. Evaluate GLM model by computing MSE and R2 values

   select * from TD_RegressionEvaluator (
   on glm_predict_out_modified as InputTable
   USING
   ObservationColumn('rainfalltomorrow')
   PredictionColumn('prediction')
   Metrics('MSE','R2')
   ) as dt;

    """
}