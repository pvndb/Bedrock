import streamlit as st
import boto3
import pandas as pd
import json
import os
from botocore.exceptions import ClientError

import boto3
import json
import pandas as pd

# Initialize Bedrock client
bedrock = boto3.client(
    service_name='bedrock-agent-runtime',
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)


prompt = """
You are a financial analyst. I will provide you with a set of contract details and invoice statements. The user will then ask you a question. Your task is to reconcile the contract fee statements and invoice fee rates for Crimson Targa, identifying any discrepancies based on the following steps:
1. Fee Rate Analysis:
- Extract the contract fee rates from the “Fee Escalation” section in ARTICLE V - FEES of the contract document (PDF)
- Apply the appropriate fee escalation based on the following Consumer Price Index for Urban Consumers (CPI-U) Annual Percent Change Average:
 - 2022: 4.7%
 - 2023: 8.01%
 - 2024: 4.1%
2.Escalation Calculation
- Identify the relevant Date from Invoice
- Apply CPI-U escalation only for years that have passed before the inoivce date :
 - For Example :
 - If the inovice data is in Dec 2023, apply the 2022 CPI-U adjustment and then apply the 2023 CPI-U adjustment
 - If you wanted to calculate the Gathering Fee for 2023, and the CPI-U Annual Percent Change Average was 3% for 2022, 2.5% for 2023, you would calculate it as follows:2022 rate: $0.20 * (1 + 0.03) * (1+2.5%)
3. Comparison of Fee Rates
- Gather the fee rates from both the contract (after applying escalations) and the corresponding invoice.
- Compare the escalated contract fee rates against the invoice fee rates for any discrepancies
Here are the search results in numbered order:
$search_results$
$output_format_instructions$



"""

def query_knowledge_base(kb_id, query, prompt,metadata_filters=None):
    if metadata_filters:
            print(metadata_filters)
    try:
        response = bedrock.retrieve_and_generate(
            input={"text": query},
            retrieveAndGenerateConfiguration={
                "type" : 'KNOWLEDGE_BASE',
                "knowledgeBaseConfiguration":{
                        "knowledgeBaseId":kb_id,
                         "generationConfiguration":{
                             'promptTemplate': {
                                  'textPromptTemplate': prompt
                         }
                         },
                        "modelArn": f"arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                        "retrievalConfiguration": {
                            "vectorSearchConfiguration": {
                                "numberOfResults": 5,
                                "overrideSearchType": "HYBRID",
                                "filter":  metadata_filters
                            }
                        },
            }
        }
        )

        
           # payload["retrieveAndGenerateConfiguration"] = metadata_filters
        
        #response = bedrock.retrieve_and_generate(**payload)
       
        return response["output"]["text"]
    except ClientError as e:
        st.error(f"An error occurred: {e}")
        return None

# Streamlit UI
st.title("Intelligent Document Processing Demo")

# Knowledge base ID input
kb_id = st.text_input("Enter Knowledge Base ID", value=os.environ.get('BEDROCK_KB_ID', ''))
print(kb_id)
# Metadata filter options
st.subheader("Metadata Filters")
metadata_fields = ["Vendor", "Tag", "operator", "meter", "table"]
selected_filters = {}
combined_filters_list=[]
field_list = [] 
value_list_all=[] # save for all the value filled in the filter 
combined_filter = {"andAll":[]}
for field in metadata_fields:
    
    col1, col2 = st.columns(2)
    with col1:
        use_filter = st.checkbox(f"Use {field} filter")
    with col2:
        if use_filter:
            value = st.text_input(f"{field} value")
            if value:
                value_list = value.split(',')
                
                selected_filters["in"] = {'key':field,'value':value_list}

                field_list.append(field)
   
                value_list_all.append(value_list)
               


print(f"field_list:{field_list}")
print(f"value_list_all:{value_list_all}")

for i in range(len(field_list)):
    d = {'in': {'key': field_list[i], 'value': value_list_all[i]}}
    combined_filter ['andAll'].append(d)


print(f"combined_filter:{combined_filter}")
# for i in combined_filters_list:
#     combined_filter["in"].append(i["in"])
# print(f"combined_filter:{combined_filter}")

                #selected_filters["equals"] = {'key':field,'value':value}

# Query input
st.subheader("Reconciliation Query")
default_query = """Calculate the fee rates based on the contract and applied annual escalation rate and compare that with the fee rates in invoice table.
Format the response as a JSON array of objects and only give the JSON array output"""
query = st.text_area("Enter your reconciliation query", value=default_query)

if st.button("Process Documents"):
    if not kb_id:
        st.error("Please enter a Knowledge Base ID")
    elif not query:
        st.error("Please enter a reconciliation query")
    else:
        with st.spinner('Processing...'):
            # Query the knowledge base
            results = query_knowledge_base(kb_id, query,prompt,combined_filter)
            print(results)
            # Process and display results
            if results:
                st.subheader("Reconciliation Results")
                
                # Attempt to parse the response as JSON
                try:
                    reconciliation_data = json.loads(results)
                    
                    #Display results in a modular format
                    for item in reconciliation_data:
                        with st.expander(f"Discrepancy for Contract {item.get('contract_id', 'Unknown')} and Invoice {item.get('invoice_id', 'Unknown')}"):
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Expected Fee", item.get('expected_fee', 'N/A'))
                            col2.metric("Invoiced Amount", item.get('invoiced_amount', 'N/A'))
                            col3.metric("Discrepancy", item.get('discrepancy', 'N/A'))
                            
                            if 'notes' in item:
                                st.write("Notes:", item['notes'])
                    
                    # Display summary table
                    st.subheader("Summary Table")
                    df = pd.DataFrame(reconciliation_data)
                    st.dataframe(df)

                #st.text_input(results)
                    
                except json.JSONDecodeError:
                    st.warning("The response couldn't be parsed as JSON. Displaying raw content:")
                    st.write(results[0]['content'])
            else:
                st.info("No results found. Try adjusting your query or metadata filters.")

# Add explanatory text
st.markdown("""
## How to use this demo:
1. Enter your Knowledge Base ID (or set it as an environment variable).
2. Select and set metadata filters to refine your search (optional).
3. Modify the reconciliation query if needed. The default query asks for discrepancies between contract fees and invoice amounts.
4. Click 'Process Documents' to see the results.

The results will show discrepancies between contract fees and invoice amounts in both an expandable format and a summary table.
""")
